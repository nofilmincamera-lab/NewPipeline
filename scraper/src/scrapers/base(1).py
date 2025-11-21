"""
Base scraper class with common functionality
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from urllib.parse import urlparse, urljoin, urlunparse
import hashlib
import time


class BaseScraper(ABC):
    """Base class for all scrapers"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.rate_limit = config.get('rate_limit', 5)
        self.max_retries = config.get('max_retries', 3)
        self.retry_delays = config.get('retry_delays', [5, 15, 45])
        self.timeout = config.get('timeout', 30)
        
    @abstractmethod
    async def scrape(self, url: str) -> Dict[str, Any]:
        """Scrape a single URL"""
        pass
    
    def normalize_url(self, url: str, base_url: Optional[str] = None) -> str:
        """Normalize URL"""
        if base_url:
            url = urljoin(base_url, url)
        
        parsed = urlparse(url)
        # Remove fragment
        normalized = urlunparse((
            parsed.scheme,
            parsed.netloc.lower(),
            parsed.path,
            parsed.params,
            parsed.query,
            ''  # Remove fragment
        ))
        return normalized
    
    def get_domain(self, url: str) -> str:
        """Extract domain from URL"""
        parsed = urlparse(url)
        domain = parsed.netloc.lower().replace('www.', '')
        return domain
    
    def generate_content_hash(self, content: str) -> str:
        """Generate SHA256 hash of content"""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
    
    def should_follow_link(self, url: str, base_domain: str, max_depth: int, current_depth: int) -> bool:
        """Determine if a link should be followed"""
        if current_depth >= max_depth:
            return False
        
        link_domain = self.get_domain(url)
        return link_domain == base_domain

