"""
Scraper modules for different scraping strategies
"""

from .base import BaseScraper
from .domain_crawler import DomainCrawler
from .file_scraper import FileScraper

__all__ = ["BaseScraper", "DomainCrawler", "FileScraper"]
