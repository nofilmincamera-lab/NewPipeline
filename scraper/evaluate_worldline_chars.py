#!/usr/bin/env python3
"""
Evaluate 20 Worldline records for character count
"""

import asyncio
import os
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))

import yaml
import asyncpg
from loguru import logger
import json


async def evaluate_worldline_chars():
    """Evaluate character counts for 20 Worldline records."""
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
        # Get 20 Worldline records (both domains)
        logger.info("\n" + "="*80)
        logger.info("20 WORLDLINE RECORDS - CHARACTER COUNT ANALYSIS")
        logger.info("="*80)
        
        worldline_records = await conn.fetch("""
            SELECT url, domain, title, status_code, success, 
                   scraped_at, response_time, proxy_used, metadata
            FROM scraped_sites
            WHERE domain IN ('worldline.com', 'docs.connect.worldline-solutions.com')
            ORDER BY scraped_at DESC
            LIMIT 20
        """)
        
        if not worldline_records:
            logger.warning("No Worldline records found in database!")
            return
        
        logger.info(f"\nFound {len(worldline_records)} records\n")
        
        total_html_chars = 0
        total_content_chars = 0
        
        for i, record in enumerate(worldline_records, 1):
            logger.info(f"{'='*80}")
            logger.info(f"Record {i}/{len(worldline_records)}")
            logger.info(f"{'='*80}")
            logger.info(f"URL: {record['url']}")
            logger.info(f"Domain: {record['domain']}")
            logger.info(f"Title: {record['title'] or 'N/A'}")
            logger.info(f"Status Code: {record['status_code']}")
            logger.info(f"Success: {record['success']}")
            logger.info(f"Proxy Used: {record['proxy_used']}")
            logger.info(f"Response Time: {record['response_time']:.3f}s" if record['response_time'] else "Response Time: N/A")
            logger.info(f"Scraped At: {record['scraped_at']}")
            
            # Parse metadata for character counts
            html_length = 0
            main_content_length = 0
            
            if record['metadata']:
                try:
                    meta = json.loads(record['metadata']) if isinstance(record['metadata'], str) else record['metadata']
                    html_length = meta.get('html_length', 0)
                    main_content_length = meta.get('main_content_length', 0)
                    
                    logger.info(f"\nCharacter Counts:")
                    logger.info(f"  HTML Length: {html_length:,} characters")
                    logger.info(f"  Main Content Length: {main_content_length:,} characters")
                    
                    if html_length > 0:
                        content_ratio = (main_content_length / html_length) * 100
                        logger.info(f"  Content Ratio: {content_ratio:.2f}%")
                    
                    total_html_chars += html_length
                    total_content_chars += main_content_length
                    
                except Exception as e:
                    logger.warning(f"  Could not parse metadata: {e}")
            else:
                logger.info("  No metadata available")
            
            logger.info("")
        
        # Summary statistics
        logger.info("="*80)
        logger.info("SUMMARY STATISTICS")
        logger.info("="*80)
        logger.info(f"Total Records Analyzed: {len(worldline_records)}")
        logger.info(f"Total HTML Characters: {total_html_chars:,}")
        logger.info(f"Total Main Content Characters: {total_content_chars:,}")
        logger.info(f"Average HTML Length: {total_html_chars // len(worldline_records):,} characters")
        logger.info(f"Average Main Content Length: {total_content_chars // len(worldline_records):,} characters")
        
        if total_html_chars > 0:
            avg_content_ratio = (total_content_chars / total_html_chars) * 100
            logger.info(f"Average Content Ratio: {avg_content_ratio:.2f}%")
        
        # Breakdown by domain
        logger.info("\n" + "="*80)
        logger.info("BREAKDOWN BY DOMAIN")
        logger.info("="*80)
        
        domain_stats = await conn.fetch("""
            SELECT domain,
                   COUNT(*) as count,
                   AVG((metadata->>'html_length')::int) as avg_html,
                   AVG((metadata->>'main_content_length')::int) as avg_content,
                   SUM((metadata->>'html_length')::int) as total_html,
                   SUM((metadata->>'main_content_length')::int) as total_content
            FROM scraped_sites
            WHERE domain IN ('worldline.com', 'docs.connect.worldline-solutions.com')
            GROUP BY domain
        """)
        
        for stat in domain_stats:
            logger.info(f"\n{stat['domain']}:")
            logger.info(f"  Total Records: {stat['count']}")
            logger.info(f"  Avg HTML Length: {int(stat['avg_html'] or 0):,} characters")
            logger.info(f"  Avg Content Length: {int(stat['avg_content'] or 0):,} characters")
            logger.info(f"  Total HTML: {int(stat['total_html'] or 0):,} characters")
            logger.info(f"  Total Content: {int(stat['total_content'] or 0):,} characters")
        
        logger.info("\n" + "="*80)
        
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
    asyncio.run(evaluate_worldline_chars())

