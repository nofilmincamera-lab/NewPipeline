"""
Domain Crawler - Crawls all pages within a domain
"""

import asyncio
import time
from typing import Dict, Any, Set, Optional, List
from urllib.parse import urlparse, urljoin
from datetime import datetime
import json
import hashlib

from curl_cffi import requests
from bs4 import BeautifulSoup
from loguru import logger
import asyncpg

from .base import BaseScraper


class DomainCrawler(BaseScraper):
    """Crawls all pages within a domain"""
    
    def __init__(
        self,
        config: Dict[str, Any],
        db_connection: asyncpg.Connection,
        max_depth: int = 5,
        max_pages: int = 2000,
        max_duration_seconds: int = 7200
    ):
        super().__init__(config)
        self.db = db_connection
        self.max_depth = max_depth
        self.max_pages = max_pages
        self.max_duration_seconds = max_duration_seconds
        
        # Browser config
        self.browser_enabled = config.get('browser', {}).get('enabled', False)
        
        # Tracking
        self.visited_urls: Set[str] = set()
        self.pages_crawled = 0
        self.pages_failed = 0
        self.files_found = 0
        self.start_time = time.time()
        
    async def crawl(self, start_url: str) -> Dict[str, Any]:
        """Crawl a domain starting from start_url"""
        self.start_time = time.time()
        domain = self.get_domain(start_url)
        
        logger.info(f"Starting crawl of {domain} from {start_url}")
        
        # Normalize start URL
        start_url = self.normalize_url(start_url)
        
        # Queue for BFS crawling
        queue: List[tuple[str, int]] = [(start_url, 0)]  # (url, depth)
        
        while queue and self.pages_crawled < self.max_pages:
            # Check duration limit
            if time.time() - self.start_time > self.max_duration_seconds:
                logger.warning(f"Duration limit reached for {domain}")
                break
            
            url, depth = queue.pop(0)
            
            # Skip if already visited
            if url in self.visited_urls:
                continue
            
            self.visited_urls.add(url)
            logger.info(f"Crawling [{depth}] {url}")
            
            try:
                # Scrape the page
                result = await self.scrape(url)
                
                if result.get('success'):
                    self.pages_crawled += 1
                    
                    # Save to database
                    await self.save_to_db(result)
                    
                    # Extract links if HTML page
                    if result.get('content_type', '').startswith('text/html'):
                        links = self.extract_links(result.get('content', ''), url, domain)
                        
                        # Add new links to queue
                        for link in links:
                            if link not in self.visited_urls and depth < self.max_depth:
                                queue.append((link, depth + 1))
                    
                    # Check if it's a file
                    if result.get('file_path'):
                        self.files_found += 1
                        
                else:
                    self.pages_failed += 1
                    
            except Exception as e:
                logger.error(f"Error crawling {url}: {e}")
                self.pages_failed += 1
                await self.save_error_to_db(url, domain, str(e))
            
            # Rate limiting
            await asyncio.sleep(1.0 / self.rate_limit)
        
        duration = time.time() - self.start_time
        
        return {
            'domain': domain,
            'pages_crawled': self.pages_crawled,
            'pages_failed': self.pages_failed,
            'files_found': self.files_found,
            'duration_seconds': duration
        }
    
    async def scrape(self, url: str) -> Dict[str, Any]:
        """Scrape a single URL"""
        start_time = time.time()
        domain = self.get_domain(url)
        
        try:
            # Make request
            response = requests.get(
                url,
                timeout=self.timeout,
                impersonate="chrome110",  # curl-cffi browser impersonation
                allow_redirects=True
            )
            
            response_time = time.time() - start_time
            status_code = response.status_code
            
            # Check if successful
            if status_code != 200:
                return {
                    'url': url,
                    'domain': domain,
                    'success': False,
                    'status_code': status_code,
                    'error_message': f'HTTP {status_code}',
                    'response_time': response_time
                }
            
            # Check content type
            content_type = response.headers.get('Content-Type', '').split(';')[0].strip()
            
            # Check if it's a file to download
            file_types = self.config.get('file_download', {}).get('file_types', ['pdf', 'doc', 'docx'])
            is_file = any(url.lower().endswith(f'.{ext}') for ext in file_types)
            
            if is_file and self.config.get('file_download', {}).get('enabled', False):
                return await self.handle_file_download(url, domain, response, response_time)
            
            # Parse HTML content
            content = response.text
            soup = BeautifulSoup(content, 'lxml')
            
            # Extract title
            title_tag = soup.find('title')
            title = title_tag.get_text(strip=True) if title_tag else None
            
            # Extract main text content
            # Remove script and style elements
            for script in soup(["script", "style", "meta", "link"]):
                script.decompose()
            
            text_content = soup.get_text(separator=' ', strip=True)
            
            # Generate content hash
            content_hash = self.generate_content_hash(text_content) if text_content else None
            
            # Extract metadata
            metadata = {
                'content_type': content_type,
                'content_length': len(text_content) if text_content else 0,
                'response_headers': dict(response.headers),
                'scraped_at': datetime.now().isoformat()
            }
            
            return {
                'url': url,
                'domain': domain,
                'title': title,
                'content': text_content,
                'content_hash': content_hash,
                'content_type': content_type,
                'success': True,
                'status_code': status_code,
                'response_time': response_time,
                'metadata': metadata,
                'strategy': 'http'  # Using HTTP, not browser
            }
            
        except Exception as e:
            response_time = time.time() - start_time
            logger.error(f"Error scraping {url}: {e}")
            return {
                'url': url,
                'domain': domain,
                'success': False,
                'error_message': str(e),
                'response_time': response_time,
                'strategy': 'http'
            }
    
    async def handle_file_download(
        self,
        url: str,
        domain: str,
        response: requests.Response,
        response_time: float
    ) -> Dict[str, Any]:
        """Handle file download"""
        # For now, just record the file URL
        # Full file download implementation would save to disk
        metadata = {
            'content_type': response.headers.get('Content-Type', ''),
            'content_length': len(response.content),
            'is_file': True,
            'scraped_at': datetime.now().isoformat()
        }
        
        return {
            'url': url,
            'domain': domain,
            'success': True,
            'status_code': response.status_code,
            'response_time': response_time,
            'metadata': metadata,
            'file_path': None,  # Would be set if file was downloaded
            'strategy': 'http'
        }
    
    def extract_links(self, html_content: str, base_url: str, domain: str) -> List[str]:
        """Extract links from HTML content"""
        soup = BeautifulSoup(html_content, 'lxml')
        links = []
        
        for tag in soup.find_all('a', href=True):
            href = tag['href']
            full_url = self.normalize_url(href, base_url)
            
            # Only include links from same domain
            if self.get_domain(full_url) == domain:
                links.append(full_url)
        
        return links
    
    async def save_to_db(self, result: Dict[str, Any]) -> None:
        """Save scraping result to database"""
        try:
            metadata_json = json.dumps(result.get('metadata', {}))
            
            await self.db.execute("""
                INSERT INTO scraped_sites (
                    url, domain, title, content_hash, scraped_at,
                    strategy, status_code, response_time, success,
                    error_message, proxy_used, cost, metadata
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13::jsonb)
                ON CONFLICT (url) DO UPDATE SET
                    title = EXCLUDED.title,
                    content_hash = EXCLUDED.content_hash,
                    scraped_at = EXCLUDED.scraped_at,
                    strategy = EXCLUDED.strategy,
                    status_code = EXCLUDED.status_code,
                    response_time = EXCLUDED.response_time,
                    success = EXCLUDED.success,
                    error_message = EXCLUDED.error_message,
                    metadata = EXCLUDED.metadata,
                    updated_at = CURRENT_TIMESTAMP
            """,
                result['url'],
                result['domain'],
                result.get('title'),
                result.get('content_hash'),
                datetime.now(),
                result.get('strategy', 'http'),
                result.get('status_code'),
                result.get('response_time'),
                result.get('success', False),
                result.get('error_message'),
                False,  # proxy_used
                0.0,    # cost
                metadata_json
            )
        except Exception as e:
            logger.error(f"Error saving to database: {e}")
    
    async def save_error_to_db(self, url: str, domain: str, error_message: str) -> None:
        """Save error to database"""
        try:
            await self.db.execute("""
                INSERT INTO scraped_sites (
                    url, domain, scraped_at, strategy, success,
                    error_message, proxy_used, cost
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                ON CONFLICT (url) DO UPDATE SET
                    success = EXCLUDED.success,
                    error_message = EXCLUDED.error_message,
                    updated_at = CURRENT_TIMESTAMP
            """,
                url,
                domain,
                datetime.now(),
                'http',
                False,
                error_message,
                False,
                0.0
            )
        except Exception as e:
            logger.error(f"Error saving error to database: {e}")

