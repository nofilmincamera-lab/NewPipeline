#!/usr/bin/env python3
"""
Test script for domain crawling with file extraction
"""

import asyncio
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

import yaml
import asyncpg
from loguru import logger
from dotenv import load_dotenv

from src.scrapers.domain_crawler import DomainCrawler


async def main():
    """Run a test crawl."""
    # Load configuration
    config_path = Path(__file__).parent / 'config' / 'scraper_config.yaml'
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    # Database connection
    db_host = os.getenv('POSTGRES_HOST', config['storage']['db_host'])
    db_name = os.getenv('POSTGRES_DB', config['storage']['db_name'])
    db_user = os.getenv('POSTGRES_USER', config['storage']['db_user'])
    
    # Read password from secret file or environment
    password_file = os.getenv('POSTGRES_PASSWORD_FILE', '/run/secrets/postgres_password')
    if os.path.exists(password_file):
        with open(password_file, 'r') as f:
            db_password = f.read().strip()
    else:
        db_password = os.getenv('POSTGRES_PASSWORD', 'bpo_secure_password_2025')
    
    # Connect to database
    logger.info(f"Connecting to database {db_name}@{db_host}...")
    conn = await asyncpg.connect(
        host=db_host,
        database=db_name,
        user=db_user,
        password=db_password
    )
    
    try:
        # Get test URL from command line or use default
        if len(sys.argv) > 1:
            test_url = sys.argv[1]
        else:
            # Read first URL from sites file
            sites_file = Path(__file__).parent / 'config' / 'bpo_sites.txt'
            with open(sites_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        test_url = line
                        break
                else:
                    logger.error("No URLs found in bpo_sites.txt")
                    return
        
        logger.info(f"Starting test crawl of: {test_url}")
        
        # Create crawler
        crawler = DomainCrawler(
            config=config,
            db_connection=conn,
            max_depth=2,  # Start with depth 2 for testing
            max_pages=20  # Limit to 20 pages for testing
        )
        
        # Run crawl
        results = await crawler.crawl(test_url)
        
        # Print results
        logger.info("\n" + "="*60)
        logger.info("CRAWL RESULTS")
        logger.info("="*60)
        logger.info(f"Domain: {results['domain']}")
        logger.info(f"Pages crawled: {results['pages_crawled']}")
        logger.info(f"Pages failed: {results['pages_failed']}")
        logger.info(f"Files found: {results['files_found']}")
        logger.info(f"Duration: {results.get('duration_seconds', 0):.1f} seconds")
        logger.info("="*60)
        
    finally:
        await conn.close()


if __name__ == '__main__':
    # Configure logging
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
        level="INFO"
    )
    
    # Run async main
    asyncio.run(main())

