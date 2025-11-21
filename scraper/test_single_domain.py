#!/usr/bin/env python3
"""Test script to scrape a single domain"""

import asyncio
import os
import sys
from pathlib import Path
import yaml
import asyncpg
from loguru import logger
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).parent))

from src.scrapers.domain_crawler import DomainCrawler

async def main():
    # Load config
    config_path = Path(__file__).parent / 'config' / 'scraper_config.yaml'
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    # Database connection
    db_host = os.getenv('POSTGRES_HOST', 'postgres')
    db_name = os.getenv('POSTGRES_DB', 'bpo_intelligence')
    db_user = os.getenv('POSTGRES_USER', 'bpo_user')
    
    password_file = '/run/secrets/postgres_password'
    with open(password_file, 'r') as f:
        db_password = f.read().strip()
    
    conn = await asyncpg.connect(
        host=db_host,
        database=db_name,
        user=db_user,
        password=db_password
    )
    
    try:
        # Test with a single domain
        test_url = 'https://www.accenture.com'
        logger.info(f"Testing crawl of {test_url}")
        
        crawler = DomainCrawler(
            config=config,
            db_connection=conn,
            max_depth=2,  # Shallow for testing
            max_pages=10,  # Limit pages for testing
            max_duration_seconds=300
        )
        
        results = await crawler.crawl(test_url)
        
        logger.info(f"\nResults:")
        logger.info(f"  Pages crawled: {results['pages_crawled']}")
        logger.info(f"  Pages failed: {results['pages_failed']}")
        logger.info(f"  Files found: {results['files_found']}")
        logger.info(f"  Duration: {results['duration_seconds']:.1f}s")
        
    finally:
        await conn.close()

if __name__ == '__main__':
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    asyncio.run(main())


