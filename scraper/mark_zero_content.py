#!/usr/bin/env python3
"""
Mark zero content pages for rescrape planning.
Can be run independently to analyze existing data.
"""

import asyncio
import os
import sys
import json
from pathlib import Path
from datetime import datetime
import asyncpg
from loguru import logger


async def mark_zero_content_pages(db_conn: asyncpg.Connection, domain: str = None) -> dict:
    """
    Mark pages with 0 content for rescrape planning.
    Returns summary statistics.
    """
    # Build query
    if domain:
        parsed = urlparse(domain if domain.startswith('http') else f'https://{domain}')
        domain_name = parsed.netloc.lower().replace('www.', '')
        domain_filter = "AND domain = $1"
        params = [domain_name]
    else:
        domain_filter = ""
        params = []
    
    # Find pages with 0 content
    query = f"""
        SELECT id, url, domain, title, content_hash, metadata
        FROM scraped_sites
        WHERE success = true
          AND (title IS NULL OR title = '')
          AND (content_hash IS NULL OR content_hash = '')
          AND (metadata->>'content_length' IS NULL 
               OR (metadata->>'content_length')::text = '0'
               OR (metadata->>'content_length')::text = 'null')
          AND file_path IS NULL
          AND (metadata->>'needs_rescrape' IS NULL OR metadata->>'needs_rescrape' = 'false')
          {domain_filter}
    """
    
    zero_content_pages = await db_conn.fetch(query, *params)
    
    if not zero_content_pages:
        return {'marked': 0, 'by_domain': {}}
    
    # Mark each page for rescrape
    marked_count = 0
    by_domain = {}
    
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
        domain = page['domain']
        by_domain[domain] = by_domain.get(domain, 0) + 1
    
    return {'marked': marked_count, 'by_domain': by_domain}


async def get_zero_content_summary(db_conn: asyncpg.Connection) -> dict:
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
    """Mark zero content pages for rescrape."""
    # Database connection
    db_host = os.getenv('POSTGRES_HOST', 'localhost')
    db_name = os.getenv('POSTGRES_DB', 'bpo_intelligence')
    db_user = os.getenv('POSTGRES_USER', 'bpo_user')
    
    # Read password
    password_file = os.getenv('POSTGRES_PASSWORD_FILE', '/run/secrets/postgres_password')
    if os.path.exists(password_file):
        with open(password_file, 'r') as f:
            db_password = f.read().strip()
    else:
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
        # Check total pages
        total_pages = await conn.fetchval("SELECT COUNT(*) FROM scraped_sites WHERE success = true")
        logger.info(f"Total successful scrapes: {total_pages}")
        
        # Mark zero content pages
        logger.info("\nMarking zero content pages for rescrape...")
        result = await mark_zero_content_pages(conn)
        
        logger.info(f"\n{'='*80}")
        logger.info("MARKING SUMMARY")
        logger.info(f"{'='*80}")
        logger.info(f"Total pages marked: {result['marked']}")
        
        if result['by_domain']:
            logger.info("\nBy domain:")
            for domain, count in sorted(result['by_domain'].items(), key=lambda x: x[1], reverse=True):
                logger.info(f"  {domain}: {count} pages")
        
        # Get final summary
        logger.info(f"\n{'='*80}")
        logger.info("ZERO CONTENT PAGES SUMMARY (All Marked Pages)")
        logger.info(f"{'='*80}")
        summary = await get_zero_content_summary(conn)
        logger.info(f"Total zero-content pages marked: {summary['total']}")
        if summary['by_domain']:
            logger.info("\nBy domain:")
            for domain, count in sorted(summary['by_domain'].items(), key=lambda x: x[1], reverse=True):
                logger.info(f"  {domain}: {count} pages")
        else:
            logger.info("  No zero-content pages found.")
        
        logger.info(f"{'='*80}\n")
        
    finally:
        await conn.close()


if __name__ == '__main__':
    from urllib.parse import urlparse
    
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
        level="INFO"
    )
    
    asyncio.run(main())

