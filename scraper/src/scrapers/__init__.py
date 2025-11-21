"""
Scraper modules for different scraping strategies
"""

# Note: Scraper modules are dynamically loaded from Docker or when available
try:
    from .base import BaseScraper
    from .domain_crawler import DomainCrawler
    __all__ = ["BaseScraper", "DomainCrawler"]
except ImportError:
    # Modules may be in Docker or need to be created
    __all__ = []
