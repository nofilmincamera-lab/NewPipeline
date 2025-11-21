#!/usr/bin/env python3
"""
Evaluate scraping results - pull random records and check for downloaded files
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


async def evaluate_results():
    """Evaluate scraping results."""
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
        # Get summary statistics
        logger.info("\n" + "="*80)
        logger.info("SCRAPING RESULTS SUMMARY")
        logger.info("="*80)
        
        # Total records
        total_count = await conn.fetchval("SELECT COUNT(*) FROM scraped_sites")
        logger.info(f"Total pages scraped: {total_count}")
        
        # By domain
        domain_stats = await conn.fetch("""
            SELECT domain, COUNT(*) as count, 
                   COUNT(CASE WHEN success = true THEN 1 END) as successful,
                   COUNT(CASE WHEN success = false THEN 1 END) as failed
            FROM scraped_sites
            GROUP BY domain
            ORDER BY count DESC
        """)
        
        logger.info("\nBy Domain:")
        for row in domain_stats:
            logger.info(f"  {row['domain']}: {row['count']} total ({row['successful']} successful, {row['failed']} failed)")
        
        # Get 5 random records
        logger.info("\n" + "="*80)
        logger.info("5 RANDOM SCRAPED RECORDS")
        logger.info("="*80)
        
        random_records = await conn.fetch("""
            SELECT url, domain, title, status_code, success, 
                   scraped_at, response_time, proxy_used, metadata
            FROM scraped_sites
            ORDER BY RANDOM()
            LIMIT 5
        """)
        
        for i, record in enumerate(random_records, 1):
            logger.info(f"\n--- Record {i} ---")
            logger.info(f"URL: {record['url']}")
            logger.info(f"Domain: {record['domain']}")
            logger.info(f"Title: {record['title'] or 'N/A'}")
            logger.info(f"Status Code: {record['status_code']}")
            logger.info(f"Success: {record['success']}")
            logger.info(f"Proxy Used: {record['proxy_used']}")
            logger.info(f"Response Time: {record['response_time']:.3f}s" if record['response_time'] else "Response Time: N/A")
            logger.info(f"Scraped At: {record['scraped_at']}")
            if record['metadata']:
                try:
                    meta = json.loads(record['metadata']) if isinstance(record['metadata'], str) else record['metadata']
                    logger.info(f"Metadata: {json.dumps(meta, indent=2)}")
                except:
                    logger.info(f"Metadata: {record['metadata']}")
        
        # Check for downloaded files
        logger.info("\n" + "="*80)
        logger.info("FILE DOWNLOAD CHECK")
        logger.info("="*80)
        
        # Check database for downloaded files
        file_count = await conn.fetchval("SELECT COUNT(*) FROM downloaded_files")
        logger.info(f"Files in database: {file_count}")
        
        if file_count > 0:
            file_records = await conn.fetch("""
                SELECT url, file_name, file_type, file_size, downloaded_at, status
                FROM downloaded_files
                ORDER BY downloaded_at DESC
                LIMIT 10
            """)
            logger.info("\nRecent downloaded files:")
            for file_rec in file_records:
                logger.info(f"  - {file_rec['file_name']} ({file_rec['file_type']}, {file_rec['file_size']} bytes) from {file_rec['url']}")
        
        # Check file system for downloaded files
        file_storage_path = config.get('file_download', {}).get('file_storage_path', '/app/data/files')
        # Try relative path
        if not Path(file_storage_path).exists():
            file_storage_path = Path(__file__).parent.parent / 'data' / 'scraped' / 'files'
        
        logger.info(f"\nChecking file storage path: {file_storage_path}")
        
        if Path(file_storage_path).exists():
            # Count files by type
            pdf_files = list(Path(file_storage_path).rglob('*.pdf'))
            doc_files = list(Path(file_storage_path).rglob('*.doc'))
            docx_files = list(Path(file_storage_path).rglob('*.docx'))
            
            total_files = len(pdf_files) + len(doc_files) + len(docx_files)
            logger.info(f"Files found on disk:")
            logger.info(f"  PDF: {len(pdf_files)}")
            logger.info(f"  DOC: {len(doc_files)}")
            logger.info(f"  DOCX: {len(docx_files)}")
            logger.info(f"  Total: {total_files}")
            
            if total_files > 0:
                logger.info("\nSample files:")
                for file_path in (pdf_files + doc_files + docx_files)[:5]:
                    size = file_path.stat().st_size
                    logger.info(f"  - {file_path.name} ({size:,} bytes) - {file_path.parent.name}")
        else:
            logger.warning(f"File storage path does not exist: {file_storage_path}")
        
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
    asyncio.run(evaluate_results())

