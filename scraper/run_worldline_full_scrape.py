#!/usr/bin/env python3
"""
Standalone full scrape of Worldline domains - bypassing Prefect.
Runs both domains with max 2000 records each, processing URLs in parallel batches of 4-6.
"""

import asyncio
import os
import sys
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime
from urllib.parse import urlparse

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))

import yaml
import asyncpg
from loguru import logger

from src.scrapers.domain_crawler import DomainCrawler


async def scrape_domain(
    url: str,
    config: dict,
    db_conn: asyncpg.Connection,
    max_pages: int = 2000,
    max_depth: int = 5
) -> Dict[str, Any]:
    """Scrape a single domain with max page limit."""
    logger.info(f"\n{'='*80}")
    logger.info(f"Starting full scrape of: {url}")
    logger.info(f"Max pages: {max_pages}, Max depth: {max_depth}")
    logger.info(f"{'='*80}\n")
    
    crawler = DomainCrawler(
        config=config,
        db_connection=db_conn,
        max_depth=max_depth,
        max_pages=max_pages,
        max_duration_seconds=7200  # 2 hours max per domain
    )
    
    results = await crawler.crawl(url)
    
    logger.info(f"\n{'='*80}")
    logger.info(f"SCRAPE RESULTS FOR {url}")
    logger.info(f"{'='*80}")
    logger.info(f"Domain: {results['domain']}")
    logger.info(f"Pages crawled: {results['pages_crawled']}")
    logger.info(f"Pages failed: {results['pages_failed']}")
    logger.info(f"Files found: {results['files_found']}")
    logger.info(f"Duration: {results.get('duration_seconds', 0):.1f} seconds")
    logger.info(f"{'='*80}\n")
    
    return results


async def main():
    """Run full scrape of both Worldline domains with parallel batch processing."""
    # Load configuration
    config_path = Path(__file__).parent / 'config' / 'scraper_config.yaml'
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    # Database connection
    db_host = os.getenv('POSTGRES_HOST', config['storage'].get('db_host', 'localhost'))
    db_name = os.getenv('POSTGRES_DB', config['storage'].get('db_name', 'bpo_intelligence'))
    db_user = os.getenv('POSTGRES_USER', config['storage'].get('db_user', 'bpo_user'))
    
    # Read password from secret file or environment
    password_file = os.getenv('POSTGRES_PASSWORD_FILE', '/run/secrets/postgres_password')
    if os.path.exists(password_file):
        with open(password_file, 'r') as f:
            db_password = f.read().strip()
    else:
        # Try local path
        local_password_file = Path(__file__).parent.parent.parent / 'ops' / 'secrets' / 'postgres_password.txt'
        if local_password_file.exists():
            with open(local_password_file, 'r') as f:
                db_password = f.read().strip()
        else:
            db_password = os.getenv('POSTGRES_PASSWORD', 'bpo_secure_password_2025')
    
    # Connect to database
    logger.info(f"Connecting to database {db_name}@{db_host}...")
    try:
        conn = await asyncpg.connect(
            host=db_host,
            database=db_name,
            user=db_user,
            password=db_password
        )
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        logger.info("Trying with default localhost settings...")
        conn = await asyncpg.connect(
            host='localhost',
            database='bpo_intelligence',
            user='bpo_user',
            password='bpo_secure_password_2025'
        )
    
    try:
        # Worldline domains to scrape
        sites = [
            'https://worldline.com',
            'https://docs.connect.worldline-solutions.com/'
        ]
        
        # Get initial record counts
        logger.info("Checking existing records...")
        for site_url in sites:
            parsed = urlparse(site_url)
            domain = parsed.netloc.lower().replace('www.', '')
            existing_count = await conn.fetchval("""
                SELECT COUNT(*) FROM scraped_sites 
                WHERE domain = $1 AND success = true
            """, domain)
            logger.info(f"  {domain}: {existing_count} existing records")
        
        all_results = {}
        start_time = datetime.now()
        
        # Process domains in parallel (batch size = number of domains)
        # Each domain will process URLs sequentially, but domains run in parallel
        tasks = []
        for site_url in sites:
            task = scrape_domain(
                site_url,
                config,
                conn,
                max_pages=2000,
                max_depth=5
            )
            tasks.append((site_url, task))
        
        # Run domains in parallel
        logger.info(f"\nStarting parallel scrape of {len(sites)} domains...\n")
        results_list = await asyncio.gather(*[task for _, task in tasks], return_exceptions=True)
        
        # Collect results
        for (site_url, _), result in zip(tasks, results_list):
            if isinstance(result, Exception):
                logger.error(f"Error scraping {site_url}: {result}")
                import traceback
                traceback.print_exc()
                all_results[site_url] = {'error': str(result)}
            else:
                all_results[site_url] = result
        
        # Final summary
        total_duration = (datetime.now() - start_time).total_seconds()
        
        logger.info(f"\n{'='*80}")
        logger.info("FINAL SUMMARY")
        logger.info(f"{'='*80}")
        
        total_pages = sum(r.get('pages_crawled', 0) for r in all_results.values() if isinstance(r, dict) and 'error' not in r)
        total_files = sum(r.get('files_found', 0) for r in all_results.values() if isinstance(r, dict) and 'error' not in r)
        total_failed = sum(r.get('pages_failed', 0) for r in all_results.values() if isinstance(r, dict) and 'error' not in r)
        
        logger.info(f"Total domains processed: {len(sites)}")
        logger.info(f"Total pages crawled: {total_pages}")
        logger.info(f"Total files found: {total_files}")
        logger.info(f"Total pages failed: {total_failed}")
        logger.info(f"Total duration: {total_duration:.1f} seconds ({total_duration/60:.1f} minutes)")
        
        # Show final record counts
        logger.info(f"\nFinal record counts:")
        for site_url in sites:
            parsed = urlparse(site_url)
            domain = parsed.netloc.lower().replace('www.', '')
            final_count = await conn.fetchval("""
                SELECT COUNT(*) FROM scraped_sites 
                WHERE domain = $1 AND success = true
            """, domain)
            logger.info(f"  {domain}: {final_count} total records")
        
        logger.info(f"{'='*80}\n")
        
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

