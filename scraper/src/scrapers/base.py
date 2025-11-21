"""
Base scraper class with common functionality
"""

import hashlib
import time
from abc import ABC, abstractmethod
from typing import Dict, Optional, Any
from urllib.parse import urlparse, urljoin
from datetime import datetime

from curl_cffi import requests
from loguru import logger


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
    
    def fetch_page(
        self,
        url: str,
        session: Optional[requests.Session] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Fetch a page with retry logic.
        
        Args:
            url: URL to fetch
            session: Optional requests session
            headers: Optional custom headers
            
        Returns:
            Dictionary with fetch results:
            {
                'success': bool,
                'url': str,
                'status_code': int,
                'content': str,
                'headers': dict,
                'response_time': float,
                'error': str
            }
        """
        if session is None:
            session = requests.Session()
        
        domain = self._get_domain(url)
        self._rate_limit_wait(domain)
        
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
        
        last_error = None
        for attempt in range(self.max_retries):
            try:
                start_time = time.time()
                
                response = session.get(
                    url,
                    headers=default_headers,
                    timeout=(self.connect_timeout, self.read_timeout),
                    allow_redirects=True,
                    max_redirects=5
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
                    'error': None
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
            'error': last_error or "Unknown error"
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

