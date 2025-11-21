"""
Base scraper class with common functionality
"""

import hashlib
import time
import os
import asyncio
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Optional, Any
from urllib.parse import urlparse, urljoin
from datetime import datetime, timedelta

from curl_cffi import requests
from loguru import logger

from ..detectors.security_detector import SecurityDetector
from .browser_fetcher import BrowserFetcher


class BaseScraper(ABC):
    """Base class for all scrapers."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize base scraper.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.timeout = config.get('timeout', 30)
        self.connect_timeout = config.get('connect_timeout', 10)
        self.read_timeout = config.get('read_timeout', 30)
        self.max_retries = config.get('max_retries', 3)
        self.retry_delays = config.get('retry_delays', [5, 15, 45])
        self.max_content_size = config.get('max_content_size', 10485760)  # 10MB
        self.rate_limit = config.get('rate_limit', 5)  # requests per second
        
        # Rate limiting tracking
        self.domain_last_request = {}
        self.min_request_interval = 1.0 / self.rate_limit
        
        # Proxy configuration
        self.proxy_strategy = config.get('proxy_strategy', 'never')
        self.proxy_used = False
        
        # Browser configuration
        browser_config = config.get('browser', {})
        self.browser_enabled = browser_config.get('enabled', True)
        self.browser_fetcher = None
        if self.browser_enabled:
            try:
                self.browser_fetcher = BrowserFetcher(
                    config=config,
                    headless=browser_config.get('headless', True),
                    timeout=browser_config.get('timeout', 30),
                    wait_strategy=browser_config.get('wait_strategy', 'networkidle'),
                    wait_timeout=browser_config.get('wait_timeout', 10),
                    enable_shadow_dom=browser_config.get('enable_shadow_dom_extraction', True),
                    enable_iframe=browser_config.get('enable_iframe_extraction', True)
                )
            except Exception as e:
                logger.warning(f"Could not initialize browser fetcher: {e}")
                self.browser_enabled = False
        
        # Security detector for pre-check
        self.security_detector = SecurityDetector()
        
        # Database connection for caching (will be set by subclasses if needed)
        self.db_connection = None
    
    def _get_domain(self, url: str) -> str:
        """Extract domain from URL."""
        parsed = urlparse(url)
        return parsed.netloc.lower()
    
    def _normalize_url(self, url: str, base_url: Optional[str] = None) -> Optional[str]:
        """
        Normalize URL to absolute form.
        
        Args:
            url: URL to normalize
            base_url: Base URL for relative URLs
            
        Returns:
            Normalized absolute URL or None if invalid
        """
        if not url:
            return None
        
        # Remove fragments
        url = url.split('#')[0].strip()
        
        # Skip non-HTTP(S) URLs
        if ':' in url and not url.startswith(('http://', 'https://')):
            return None
        
        if base_url:
            try:
                absolute_url = urljoin(base_url, url)
            except Exception:
                return None
        else:
            absolute_url = url
        
        try:
            parsed = urlparse(absolute_url)
            if not parsed.scheme or not parsed.netloc:
                return None
            return absolute_url
        except Exception:
            return None
    
    def _is_same_domain(self, url1: str, url2: str) -> bool:
        """Check if two URLs are from the same domain."""
        domain1 = self._get_domain(url1)
        domain2 = self._get_domain(url2)
        return domain1 == domain2
    
    def _rate_limit_wait(self, domain: str):
        """Wait if necessary to respect rate limits."""
        if domain in self.domain_last_request:
            elapsed = time.time() - self.domain_last_request[domain]
            if elapsed < self.min_request_interval:
                sleep_time = self.min_request_interval - elapsed
                time.sleep(sleep_time)
        
        self.domain_last_request[domain] = time.time()
    
    def _get_proxy_url(self) -> Optional[str]:
        """
        Get proxy URL based on configuration.
        
        Returns:
            Proxy URL string or None if no proxy should be used
        """
        if self.proxy_strategy == 'never':
            return None
        
        if self.proxy_strategy == 'always' or self.proxy_strategy == 'intelligent':
            # Apify proxy configuration
            proxy_host = self.config.get('apify_proxy_host', 'proxy.apify.com')
            proxy_port = self.config.get('apify_proxy_port', 8000)
            proxy_groups = self.config.get('apify_proxy_groups', 'RESIDENTIAL')
            proxy_countries = self.config.get('apify_proxy_countries', ['US'])
            
            # Get password from file or environment
            # Try multiple possible paths
            password_file = os.getenv('APIFY_PROXY_PASSWORD_FILE', '/run/secrets/apify_proxy_password')
            proxy_password = ''
            
            # Try the configured path first
            if os.path.exists(password_file):
                try:
                    with open(password_file, 'r') as f:
                        proxy_password = f.read().strip()
                except Exception:
                    pass
            
            # Try relative path from project root
            if not proxy_password:
                rel_path = Path(__file__).parent.parent.parent.parent / 'ops' / 'secrets' / 'apify_proxy_password.txt'
                if rel_path.exists():
                    try:
                        with open(rel_path, 'r') as f:
                            proxy_password = f.read().strip()
                    except Exception:
                        pass
            
            # Fall back to environment variable
            if not proxy_password:
                proxy_password = os.getenv('APIFY_PROXY_PASSWORD', '')
            
            if not proxy_password:
                logger.warning("Apify proxy password not found, skipping proxy")
                return None
            
            # Build proxy URL: http://auto:password@proxy.apify.com:8000
            # For country-specific: http://auto:password@proxy.apify.com:8000?country=US
            country = proxy_countries[0] if proxy_countries else 'US'
            proxy_url = f"http://auto:{proxy_password}@{proxy_host}:{proxy_port}?country={country}"
            
            return proxy_url
        
        return None
    
    def set_db_connection(self, db_connection):
        """Set database connection for caching browser requirements."""
        self.db_connection = db_connection
    
    async def _get_domain_browser_requirement(self, domain: str) -> Optional[Dict[str, Any]]:
        """
        Get cached browser requirement for domain from database.
        
        Args:
            domain: Domain name
            
        Returns:
            Dictionary with requirement info or None if not cached
        """
        if not self.db_connection:
            return None
        
        try:
            query = """
                SELECT requires_browser, browser_reason, updated_at
                FROM domain_proxy_requirements
                WHERE domain = $1
            """
            row = await self.db_connection.fetchrow(query, domain)
            
            if row:
                # Check if cache is still valid (7 days)
                updated_at = row['updated_at']
                if updated_at and (datetime.now() - updated_at) < timedelta(days=7):
                    return {
                        'requires_browser': row['requires_browser'],
                        'browser_reason': row['browser_reason'],
                        'cached': True
                    }
        except Exception as e:
            logger.debug(f"Error querying browser requirement cache: {e}")
        
        return None
    
    async def _save_domain_browser_requirement(
        self,
        domain: str,
        requires_browser: bool,
        reason: Optional[str] = None
    ):
        """
        Save browser requirement decision to database cache.
        
        Args:
            domain: Domain name
            requires_browser: Whether browser is required
            reason: Reason for the decision
        """
        if not self.db_connection:
            return
        
        try:
            query = """
                INSERT INTO domain_proxy_requirements (domain, requires_browser, browser_reason, updated_at)
                VALUES ($1, $2, $3, CURRENT_TIMESTAMP)
                ON CONFLICT (domain) DO UPDATE SET
                    requires_browser = EXCLUDED.requires_browser,
                    browser_reason = EXCLUDED.browser_reason,
                    updated_at = CURRENT_TIMESTAMP
            """
            await self.db_connection.execute(query, domain, requires_browser, reason)
        except Exception as e:
            logger.warning(f"Error saving browser requirement to cache: {e}")
    
    async def _should_use_browser(
        self,
        url: str,
        initial_response: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Determine if browser rendering is needed for a URL.
        
        Args:
            url: URL to check
            initial_response: Optional initial HTTP response for analysis
            
        Returns:
            Dictionary with decision:
            {
                'use_browser': bool,
                'confidence': float,
                'reason': str
            }
        """
        domain = self._get_domain(url)
        
        # Check cache first
        cached = await self._get_domain_browser_requirement(domain)
        if cached:
            return {
                'use_browser': cached['requires_browser'],
                'confidence': 0.9,  # High confidence for cached decisions
                'reason': cached['browser_reason'] or 'Cached decision'
            }
        
        # If no initial response, we can't analyze - default to False
        if not initial_response or not initial_response.get('success'):
            return {
                'use_browser': False,
                'confidence': 0.0,
                'reason': 'No initial response to analyze'
            }
        
        # Analyze initial response
        content = initial_response.get('content', '')
        status_code = initial_response.get('status_code', 200)
        headers = initial_response.get('headers', {})
        
        # Run security/content detection
        detection = self.security_detector.detect(
            url=url,
            status_code=status_code,
            headers=headers,
            content=content[:50000] if content else None,  # First 50KB for analysis
            response_time=initial_response.get('response_time')
        )
        
        # Check if browser is required
        requires_browser = detection.get('requires_browser', False)
        confidence = detection.get('confidence', 0.0)
        
        # Build reason string
        indicators = detection.get('indicators', [])
        reason = '; '.join(indicators) if indicators else 'Content analysis'
        
        # Save decision to cache
        if requires_browser and confidence > 0.6:
            await self._save_domain_browser_requirement(domain, True, reason)
        
        return {
            'use_browser': requires_browser,
            'confidence': confidence,
            'reason': reason
        }
    
    async def _fetch_with_browser(
        self,
        url: str,
        proxy_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Fetch page using browser automation.
        
        Args:
            url: URL to fetch
            proxy_url: Optional proxy URL
            
        Returns:
            Dictionary with fetch results (same format as fetch_page)
        """
        if not self.browser_enabled or not self.browser_fetcher:
            return {
                'success': False,
                'url': url,
                'status_code': None,
                'content': None,
                'headers': {},
                'response_time': None,
                'error': 'Browser fetcher not available',
                'proxy_used': proxy_url is not None
            }
        
        try:
            result = await self.browser_fetcher.fetch_with_browser(url, proxy_url)
            
            # Convert browser result to match fetch_page format
            # Browser fetcher returns 'html_content' and 'content' (text)
            # We need to use 'html_content' for HTML and 'content' for text
            if result['success']:
                # Use html_content as the main content for further processing
                # The text content is already extracted
                return {
                    'success': True,
                    'url': result['url'],
                    'status_code': result['status_code'],
                    'content': result['html_content'],  # Use HTML for boilerplate extraction
                    'text_content': result['content'],  # Keep text content separate
                    'headers': result['headers'],
                    'response_time': result['response_time'],
                    'error': None,
                    'proxy_used': result['proxy_used'],
                    'browser_used': True
                }
            else:
                return {
                    'success': False,
                    'url': result['url'],
                    'status_code': result.get('status_code'),
                    'content': None,
                    'headers': result.get('headers', {}),
                    'response_time': result.get('response_time'),
                    'error': result.get('error'),
                    'proxy_used': result.get('proxy_used', False),
                    'browser_used': True
                }
        except Exception as e:
            logger.error(f"Browser fetch error for {url}: {e}")
            return {
                'success': False,
                'url': url,
                'status_code': None,
                'content': None,
                'headers': {},
                'response_time': None,
                'error': str(e),
                'proxy_used': proxy_url is not None,
                'browser_used': True
            }
    
    def fetch_page(
        self,
        url: str,
        session: Optional[requests.Session] = None,
        headers: Optional[Dict[str, str]] = None,
        use_browser: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        Fetch a page with retry logic. Supports both HTTP and browser modes.
        
        Args:
            url: URL to fetch
            session: Optional requests session
            headers: Optional custom headers
            use_browser: Optional override to force browser mode (None = auto-detect)
            
        Returns:
            Dictionary with fetch results:
            {
                'success': bool,
                'url': str,
                'status_code': int,
                'content': str,  # HTML content
                'text_content': str,  # Text content (if browser used)
                'headers': dict,
                'response_time': float,
                'error': str,
                'browser_used': bool
            }
        """
        domain = self._get_domain(url)
        self._rate_limit_wait(domain)
        
        # Determine if browser should be used
        if use_browser is None and self.browser_enabled:
            # Try to get initial response for analysis (if DB connection available)
            if self.db_connection:
                if session is None:
                    session = requests.Session()
                
                # Quick initial fetch for analysis (don't wait for full content)
                try:
                    initial_response = self._quick_fetch(url, session, headers)
                    browser_decision = asyncio.run(self._should_use_browser(url, initial_response))
                    use_browser = browser_decision['use_browser']
                    
                    if use_browser:
                        logger.info(f"Using browser for {url} (reason: {browser_decision['reason']})")
                        # Use browser instead
                        proxy_url = self._get_proxy_url()
                        browser_result = asyncio.run(self._fetch_with_browser(url, proxy_url))
                        return browser_result
                except Exception as e:
                    logger.debug(f"Error in browser detection, falling back to HTTP: {e}")
                    use_browser = False
            else:
                # No DB connection, can't check cache - default to HTTP
                use_browser = False
        elif use_browser is True and self.browser_enabled:
            # Explicitly requested browser mode
            proxy_url = self._get_proxy_url()
            browser_result = asyncio.run(self._fetch_with_browser(url, proxy_url))
            return browser_result
        
        # Continue with HTTP client
        if session is None:
            session = requests.Session()
        
        default_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        if headers:
            default_headers.update(headers)
        
        # Get proxy URL if needed
        proxy_url = self._get_proxy_url()
        if proxy_url:
            self.proxy_used = True
            logger.debug(f"Using proxy for {url}")
        else:
            self.proxy_used = False
        
        last_error = None
        for attempt in range(self.max_retries):
            try:
                start_time = time.time()
                
                response = session.get(
                    url,
                    headers=default_headers,
                    timeout=(self.connect_timeout, self.read_timeout),
                    allow_redirects=True,
                    max_redirects=5,
                    proxies={'http': proxy_url, 'https': proxy_url} if proxy_url else None
                )
                
                response_time = time.time() - start_time
                
                # Check status code - allow 403 but log it
                if response.status_code == 404:
                    logger.warning(f"404 Not Found: {url}")
                    return {
                        'success': False,
                        'url': url,
                        'status_code': 404,
                        'content': None,
                        'headers': dict(response.headers),
                        'response_time': response_time,
                        'error': '404 Not Found'
                    }
                
                # 403 is often just bot protection, try to continue
                if response.status_code == 403:
                    logger.warning(f"403 Forbidden (may be bot protection): {url}")
                    # Continue processing - might still have content
                
                # Check content size
                content_length = response.headers.get('Content-Length')
                if content_length:
                    size = int(content_length)
                    if size > self.max_content_size:
                        error_msg = f"Content too large: {size} bytes"
                        logger.warning(f"{error_msg}: {url}")
                        return {
                            'success': False,
                            'url': url,
                            'status_code': response.status_code,
                            'content': None,
                            'headers': dict(response.headers),
                            'response_time': response_time,
                            'error': error_msg
                        }
                
                # Read content
                content = response.text
                
                # Check actual content size
                if len(content.encode('utf-8')) > self.max_content_size:
                    error_msg = f"Content too large: {len(content)} bytes"
                    logger.warning(f"{error_msg}: {url}")
                    return {
                        'success': False,
                        'url': url,
                        'status_code': response.status_code,
                        'content': None,
                        'headers': dict(response.headers),
                        'response_time': response_time,
                        'error': error_msg
                    }
                
                # Check content type
                content_type = response.headers.get('Content-Type', '').lower()
                if 'text/html' not in content_type and 'application/xhtml' not in content_type:
                    logger.debug(f"Non-HTML content type {content_type} for {url}")
                
                # Don't raise for 403 - might still have content (bot protection)
                if response.status_code != 403:
                    response.raise_for_status()
                
                return {
                    'success': True,
                    'url': response.url,  # Final URL after redirects
                    'status_code': response.status_code,
                    'content': content,
                    'headers': dict(response.headers),
                    'response_time': response_time,
                    'error': None,
                    'proxy_used': self.proxy_used,
                    'browser_used': False
                }
                
            except requests.RequestException as e:
                last_error = str(e)
                logger.warning(f"Fetch attempt {attempt + 1} failed for {url}: {last_error}")
                
                if attempt < self.max_retries - 1:
                    delay = self.retry_delays[min(attempt, len(self.retry_delays) - 1)]
                    logger.info(f"Retrying in {delay} seconds...")
                    time.sleep(delay)
                else:
                    logger.error(f"All fetch attempts failed for {url}")
        
        return {
            'success': False,
            'url': url,
            'status_code': None,
            'content': None,
            'headers': {},
            'response_time': None,
            'error': last_error or "Unknown error",
            'browser_used': False
        }
    
    def _quick_fetch(
        self,
        url: str,
        session: requests.Session,
        headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Quick fetch for analysis (only first few KB).
        
        Args:
            url: URL to fetch
            session: Requests session
            headers: Optional headers
            
        Returns:
            Dictionary with partial fetch results
        """
        default_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        if headers:
            default_headers.update(headers)
        
        try:
            proxy_url = self._get_proxy_url()
            response = session.get(
                url,
                headers=default_headers,
                timeout=(self.connect_timeout, 5),  # Shorter timeout for quick check
                allow_redirects=True,
                max_redirects=2,
                proxies={'http': proxy_url, 'https': proxy_url} if proxy_url else None,
                stream=True
            )
            
            # Read only first 50KB for analysis
            content = ''
            for chunk in response.iter_content(chunk_size=8192):
                content += chunk.decode('utf-8', errors='ignore')
                if len(content) > 50000:
                    break
            
            return {
                'success': True,
                'url': response.url,
                'status_code': response.status_code,
                'content': content,
                'headers': dict(response.headers),
                'response_time': 0.0
            }
        except Exception as e:
            return {
                'success': False,
                'url': url,
                'status_code': None,
                'content': None,
                'headers': {},
                'response_time': None,
                'error': str(e)
            }
    
    def calculate_content_hash(self, content: str) -> str:
        """Calculate SHA-256 hash of content."""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
    
    @abstractmethod
    def scrape(self, url: str) -> Dict[str, Any]:
        """
        Scrape a URL (to be implemented by subclasses).
        
        Args:
            url: URL to scrape
            
        Returns:
            Scraping results
        """
        pass

