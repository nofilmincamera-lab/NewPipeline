#!/usr/bin/env python3
"""
Full pipeline script covering all domains for providers.
Marks any 0 content pages for rescrape planning.
"""

import asyncio
import os
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
from urllib.parse import urlparse

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))

import yaml
import asyncpg
import json
from loguru import logger

try:
    from src.scrapers.domain_crawler import DomainCrawler
    DOMAIN_CRAWLER_AVAILABLE = True
except ImportError:
    DOMAIN_CRAWLER_AVAILABLE = False
    logger.warning("DomainCrawler not available. Will only mark existing zero-content pages.")


def load_provider_domains(sites_file: Path) -> List[str]:
    """Load all provider domains from sites file."""
    domains = []
    if not sites_file.exists():
        logger.warning(f"Sites file not found: {sites_file}")
        return domains
    
    with open(sites_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            # Skip empty lines and comments
            if line and not line.startswith('#'):
                # Ensure URL has protocol
                if not line.startswith(('http://', 'https://')):
                    line = 'https://' + line
                domains.append(line)
    
    logger.info(f"Loaded {len(domains)} provider domains from {sites_file}")
    return domains


async def scrape_domain(
    url: str,
    config: dict,
    db_conn: asyncpg.Connection,
    max_pages: int = 2000,
    max_depth: int = 5
) -> Dict[str, Any]:
    """Scrape a single domain with max page limit."""
    if not DOMAIN_CRAWLER_AVAILABLE:
        logger.warning(f"Cannot scrape {url}: DomainCrawler not implemented")
        return {
            'domain': url,
            'pages_crawled': 0,
            'pages_failed': 0,
            'files_found': 0,
            'error': 'DomainCrawler not available'
        }
    
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


async def mark_zero_content_pages(
    db_conn: asyncpg.Connection,
    domain: str
) -> int:
    """
    Mark pages with 0 content for rescrape planning.
    A page is considered 0 content if:
    - success = true (page was scraped successfully)
    - AND (title IS NULL OR title = '')
    - AND (content_hash IS NULL OR content_hash = '')
    - AND (metadata->>'content_length' IS NULL OR (metadata->>'content_length')::int = 0)
    - AND file_path IS NULL (not a file download)
    """
    parsed = urlparse(domain if domain.startswith('http') else f'https://{domain}')
    domain_name = parsed.netloc.lower().replace('www.', '')
    
    # Find pages with 0 content
    zero_content_pages = await db_conn.fetch("""
        SELECT id, url, title, content_hash, metadata
        FROM scraped_sites
        WHERE domain = $1
          AND success = true
          AND (title IS NULL OR title = '')
          AND (content_hash IS NULL OR content_hash = '')
          AND (metadata->>'content_length' IS NULL 
               OR (metadata->>'content_length')::text = '0'
               OR (metadata->>'content_length')::text = 'null')
          AND file_path IS NULL
          AND (metadata->>'needs_rescrape' IS NULL OR metadata->>'needs_rescrape' = 'false')
    """, domain_name)
    
    if not zero_content_pages:
        return 0
    
    # Mark each page for rescrape
    marked_count = 0
    for page in zero_content_pages:
        # Update metadata to mark for rescrape
        current_metadata = page['metadata'] or {}
        if not isinstance(current_metadata, dict):
            current_metadata = {}
        
        current_metadata['needs_rescrape'] = True
        current_metadata['rescrape_reason'] = 'zero_content'
        current_metadata['marked_at'] = datetime.now().isoformat()
        
        await db_conn.execute("""
            UPDATE scraped_sites
            SET metadata = $1::jsonb,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = $2
        """, json.dumps(current_metadata), page['id'])
        
        marked_count += 1
    
    logger.info(f"Marked {marked_count} zero-content pages for rescrape in domain: {domain_name}")
    return marked_count


async def get_zero_content_summary(db_conn: asyncpg.Connection) -> Dict[str, Any]:
    """Get summary of zero content pages across all domains."""
    summary = await db_conn.fetch("""
        SELECT 
            domain,
            COUNT(*) as zero_content_count
        FROM scraped_sites
        WHERE success = true
          AND (title IS NULL OR title = '')
          AND (content_hash IS NULL OR content_hash = '')
          AND (metadata->>'content_length' IS NULL 
               OR (metadata->>'content_length')::text = '0'
               OR (metadata->>'content_length')::text = 'null')
          AND file_path IS NULL
          AND metadata->>'needs_rescrape' = 'true'
        GROUP BY domain
        ORDER BY zero_content_count DESC
    """)
    
    total = sum(row['zero_content_count'] for row in summary)
    return {
        'total': total,
        'by_domain': {row['domain']: row['zero_content_count'] for row in summary}
    }


async def main():
    """Run full pipeline for all provider domains and mark zero content pages."""
    # Load configuration
    config_path = Path(__file__).parent / 'config' / 'scraper_config.yaml'
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    # Load provider domains
    sites_file = Path(__file__).parent / 'config' / 'bpo_sites.txt'
    provider_domains = load_provider_domains(sites_file)
    
    if not provider_domains:
        logger.error("No provider domains found. Please check bpo_sites.txt")
        return
    
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
        # Get initial record counts
        logger.info("\nChecking existing records...")
        for site_url in provider_domains:
            parsed = urlparse(site_url)
            domain = parsed.netloc.lower().replace('www.', '')
            existing_count = await conn.fetchval("""
                SELECT COUNT(*) FROM scraped_sites 
                WHERE domain = $1 AND success = true
            """, domain)
            logger.info(f"  {domain}: {existing_count} existing records")
        
        all_results = {}
        start_time = datetime.now()
        
        # Process domains sequentially to avoid overwhelming the system
        # (Can be parallelized later if needed)
        logger.info(f"\n{'='*80}")
        logger.info(f"Starting full pipeline for {len(provider_domains)} provider domains...")
        if not DOMAIN_CRAWLER_AVAILABLE:
            logger.warning("NOTE: DomainCrawler not available. Skipping scraping, only marking zero-content pages.")
        logger.info(f"{'='*80}\n")
        
        for idx, site_url in enumerate(provider_domains, 1):
            logger.info(f"\n[{idx}/{len(provider_domains)}] Processing: {site_url}")
            try:
                if DOMAIN_CRAWLER_AVAILABLE:
                    result = await scrape_domain(
                        site_url,
                        config,
                        conn,
                        max_pages=2000,
                        max_depth=5
                    )
                    all_results[site_url] = result
                else:
                    all_results[site_url] = {'skipped': 'DomainCrawler not available'}
                
                # Mark zero content pages for this domain
                marked = await mark_zero_content_pages(conn, site_url)
                if marked > 0:
                    logger.info(f"  → Marked {marked} zero-content pages for rescrape")
                
            except Exception as e:
                logger.error(f"Error processing {site_url}: {e}")
                import traceback
                traceback.print_exc()
                all_results[site_url] = {'error': str(e)}
        
        # Final summary
        total_duration = (datetime.now() - start_time).total_seconds()
        
        logger.info(f"\n{'='*80}")
        logger.info("FINAL PIPELINE SUMMARY")
        logger.info(f"{'='*80}")
        
        total_pages = sum(r.get('pages_crawled', 0) for r in all_results.values() 
                         if isinstance(r, dict) and 'error' not in r)
        total_files = sum(r.get('files_found', 0) for r in all_results.values() 
                         if isinstance(r, dict) and 'error' not in r)
        total_failed = sum(r.get('pages_failed', 0) for r in all_results.values() 
                          if isinstance(r, dict) and 'error' not in r)
        total_errors = sum(1 for r in all_results.values() 
                          if isinstance(r, dict) and 'error' in r)
        
        logger.info(f"Total domains processed: {len(provider_domains)}")
        logger.info(f"  - Successful: {len(provider_domains) - total_errors}")
        logger.info(f"  - Errors: {total_errors}")
        logger.info(f"Total pages crawled: {total_pages}")
        logger.info(f"Total files found: {total_files}")
        logger.info(f"Total pages failed: {total_failed}")
        logger.info(f"Total duration: {total_duration:.1f} seconds ({total_duration/60:.1f} minutes)")
        
        # Show final record counts
        logger.info(f"\nFinal record counts by domain:")
        for site_url in provider_domains:
            parsed = urlparse(site_url)
            domain = parsed.netloc.lower().replace('www.', '')
            final_count = await conn.fetchval("""
                SELECT COUNT(*) FROM scraped_sites 
                WHERE domain = $1 AND success = true
            """, domain)
            logger.info(f"  {domain}: {final_count} total records")
        
        # Zero content pages summary
        logger.info(f"\n{'='*80}")
        logger.info("ZERO CONTENT PAGES SUMMARY (Marked for Rescrape)")
        logger.info(f"{'='*80}")
        zero_content_summary = await get_zero_content_summary(conn)
        logger.info(f"Total zero-content pages marked: {zero_content_summary['total']}")
        if zero_content_summary['by_domain']:
            logger.info("\nBy domain:")
            for domain, count in sorted(zero_content_summary['by_domain'].items(), 
                                       key=lambda x: x[1], reverse=True):
                logger.info(f"  {domain}: {count} pages")
        else:
            logger.info("  No zero-content pages found.")
        
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

