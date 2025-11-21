"""
Domain Crawler - Crawl a website following links within the same domain
"""

import asyncio
from typing import Dict, Set, List, Optional, Any
from urllib.parse import urlparse, urljoin
from datetime import datetime
from collections import deque

import asyncpg
from curl_cffi import requests
from loguru import logger
from bs4 import BeautifulSoup

from .base import BaseScraper
from .file_scraper import FileScraper
from ..parsers.link_extractor import LinkExtractor
from ..parsers.boilerplate_detector import BoilerplateDetector


class DomainCrawler(BaseScraper):
    """Crawl a domain following links within the same domain."""
    
    def __init__(
        self,
        config: Dict[str, Any],
        db_connection: asyncpg.Connection,
        max_depth: int = 3,
        max_pages: int = 100
    ):
        """
        Initialize domain crawler.
        
        Args:
            config: Configuration dictionary
            db_connection: Database connection
            max_depth: Maximum crawl depth
            max_pages: Maximum number of pages to crawl
        """
        super().__init__(config)
        self.db = db_connection
        self.max_depth = max_depth
        self.max_pages = max_pages
        
        # Crawl state
        self.visited_urls: Set[str] = set()
        self.failed_urls: Set[str] = set()
        self.to_visit: deque = deque()
        self.crawled_count = 0
        
        # Components
        self.boilerplate_detector = BoilerplateDetector()
        
        # File scraper if enabled
        file_config = config.get('file_download', {})
        if file_config.get('enabled', False):
            storage_path = file_config.get('file_storage_path', '/app/data/files')
            self.file_scraper = FileScraper(db_connection, storage_path, config)
        else:
            self.file_scraper = None
    
    def _extract_links(self, html_content: str, base_url: str) -> Set[str]:
        """
        Extract all links from HTML content.
        
        Args:
            html_content: HTML content
            base_url: Base URL for resolving relative links
            
        Returns:
            Set of absolute URLs
        """
        links = set()
        
        try:
            soup = BeautifulSoup(html_content, 'lxml')
        except Exception:
            soup = BeautifulSoup(html_content, 'html.parser')
        
        for link in soup.find_all('a', href=True):
            href = link.get('href', '').strip()
            if not href:
                continue
            
            normalized = self._normalize_url(href, base_url)
            if normalized:
                links.add(normalized)
        
        return links
    
    def _should_crawl(self, url: str, base_domain: str) -> bool:
        """
        Determine if a URL should be crawled.
        
        Args:
            url: URL to check
            base_domain: Base domain to stay within
            
        Returns:
            True if URL should be crawled
        """
        # Already visited
        if url in self.visited_urls:
            return False
        
        # Already failed
        if url in self.failed_urls:
            return False
        
        # Check domain
        url_domain = self._get_domain(url)
        if url_domain != base_domain:
            return False
        
        # Check if it's a file (skip direct file downloads for crawling)
        parsed = urlparse(url.lower())
        path = parsed.path
        if any(path.endswith(ext) for ext in ['.pdf', '.doc', '.docx', '.jpg', '.png', '.gif', '.zip', '.exe']):
            return False
        
        # Check if it's likely a page (has .html, .htm, or no extension, or ends with /)
        if path.endswith(('.html', '.htm', '/')) or '.' not in path.split('/')[-1]:
            return True
        
        return False
    
    async def crawl(self, start_url: str) -> Dict[str, Any]:
        """
        Crawl a domain starting from a URL.
        
        Args:
            start_url: Starting URL
            
        Returns:
            Crawl results summary
        """
        base_domain = self._get_domain(start_url)
        logger.info(f"Starting crawl of {base_domain} from {start_url}")
        
        # Initialize queue
        self.to_visit.append((start_url, 0))  # (url, depth)
        self.visited_urls.add(start_url)
        
        session = requests.Session()
        results = {
            'start_url': start_url,
            'domain': base_domain,
            'pages_crawled': 0,
            'pages_failed': 0,
            'files_found': 0,
            'start_time': datetime.now(),
            'end_time': None
        }
        
        while self.to_visit and self.crawled_count < self.max_pages:
            url, depth = self.to_visit.popleft()
            
            if depth > self.max_depth:
                logger.debug(f"Skipping {url} (depth {depth} > max {self.max_depth})")
                continue
            
            logger.info(f"Crawling [{depth}] {url} ({self.crawled_count + 1}/{self.max_pages})")
            
            # Fetch page
            fetch_result = self.fetch_page(url, session=session)
            
            if not fetch_result['success']:
                self.failed_urls.add(url)
                results['pages_failed'] += 1
                
                # Skip 404s
                if fetch_result.get('status_code') == 404:
                    logger.info(f"Skipping 404: {url}")
                    continue
                
                logger.warning(f"Failed to fetch {url}: {fetch_result.get('error')} (Status: {fetch_result.get('status_code', 'N/A')})")
                continue
            
            # Check if URL redirected to different domain (normalize http/https)
            final_url = fetch_result.get('url', url)
            final_domain = self._get_domain(final_url)
            if final_domain != base_domain:
                logger.info(f"URL redirected to different domain: {url} -> {final_url} ({final_domain} != {base_domain})")
                continue
            
            # Update URL to final URL if redirected
            if final_url != url:
                url = final_url
                logger.debug(f"Following redirect: {url}")
            
            # Check if it's actually HTML
            content_type = fetch_result.get('headers', {}).get('Content-Type', '').lower()
            html_content = fetch_result['content']
            
            # If no content-type header, check if content looks like HTML
            is_html = False
            if content_type:
                is_html = 'text/html' in content_type or 'application/xhtml' in content_type
            else:
                # No content-type header - check if content looks like HTML
                html_lower = html_content[:500].lower() if html_content else ''
                is_html = '<html' in html_lower or '<!doctype' in html_lower or '<body' in html_lower
            
            if not is_html:
                logger.info(f"Skipping non-HTML content: {url} (Content-Type: {content_type or 'N/A'})")
                continue
            
            html_content = fetch_result['content']
            
            # Log content info
            logger.debug(f"Fetched {url}: {len(html_content)} bytes, status {fetch_result.get('status_code')}")
            
            # Check for boilerplate (skip if too much boilerplate)
            content_ratio = self.boilerplate_detector.get_content_ratio(html_content)
            logger.debug(f"Content ratio for {url}: {content_ratio:.2%}")
            if content_ratio < 0.1:  # Less than 10% main content
                logger.info(f"Skipping page with too much boilerplate ({content_ratio:.2%}): {url}")
                # Don't skip - might be a small page, just log it
                # continue
            
            # Extract main content
            main_content = self.boilerplate_detector.extract_main_content(html_content)
            
            # Save to database
            await self._save_page(url, fetch_result, main_content, html_content)
            
            # Extract and process file links
            if self.file_scraper:
                file_results = await self.file_scraper.process_page_for_files(
                    page_url=url,
                    html_content=html_content,
                    session=session
                )
                results['files_found'] += len([r for r in file_results if r.get('status') == 'downloaded'])
            
            # Extract links for further crawling
            if depth < self.max_depth:
                links = self._extract_links(html_content, url)
                for link in links:
                    if self._should_crawl(link, base_domain):
                        self.to_visit.append((link, depth + 1))
                        self.visited_urls.add(link)
            
            self.crawled_count += 1
            results['pages_crawled'] += 1
        
        results['end_time'] = datetime.now()
        duration = (results['end_time'] - results['start_time']).total_seconds()
        results['duration_seconds'] = duration
        
        logger.info(f"Crawl completed: {results['pages_crawled']} pages, {results['pages_failed']} failed, {results['files_found']} files found in {duration:.1f}s")
        
        return results
    
    async def _save_page(
        self,
        url: str,
        fetch_result: Dict[str, Any],
        main_content: str,
        html_content: str
    ):
        """Save page to database."""
        try:
            domain = self._get_domain(url)
            content_hash = self.calculate_content_hash(html_content)
            
            # Extract title
            try:
                soup = BeautifulSoup(html_content, 'html.parser')
                title_tag = soup.find('title')
                title = title_tag.get_text(strip=True) if title_tag else None
            except Exception:
                title = None
            
            # Insert or update in database
            query = """
                INSERT INTO scraped_sites (
                    url, domain, title, content_hash, scraped_at,
                    strategy, status_code, response_time, success,
                    error_message, proxy_used, cost, metadata
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13
                )
                ON CONFLICT (url) DO UPDATE SET
                    title = EXCLUDED.title,
                    content_hash = EXCLUDED.content_hash,
                    scraped_at = EXCLUDED.scraped_at,
                    status_code = EXCLUDED.status_code,
                    response_time = EXCLUDED.response_time,
                    success = EXCLUDED.success,
                    error_message = EXCLUDED.error_message,
                    updated_at = CURRENT_TIMESTAMP
            """
            
            await self.db.execute(
                query,
                url,
                domain,
                title,
                content_hash,
                datetime.now(),
                'domain_crawl',
                fetch_result.get('status_code'),
                fetch_result.get('response_time'),
                fetch_result['success'],
                fetch_result.get('error'),
                False,  # proxy_used
                0.0,  # cost
                {'main_content_length': len(main_content), 'html_length': len(html_content)}
            )
            
        except Exception as e:
            logger.error(f"Error saving page {url} to database: {e}")
    
    def scrape(self, url: str) -> Dict[str, Any]:
        """
        Scrape a single URL (synchronous wrapper for async crawl).
        
        Args:
            url: URL to scrape
            
        Returns:
            Scraping results
        """
        # This is a synchronous wrapper - actual crawling is async
        # For now, return a placeholder
        return {
            'success': False,
            'error': 'Use crawl() method for domain crawling'
        }

