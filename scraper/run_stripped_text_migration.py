#!/usr/bin/env python3
"""
Run database migration to add stripped_text column
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


async def run_migration():
    """Run the stripped_text migration SQL script."""
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
        # Read migration file
        migration_file = Path(__file__).parent / 'migrations' / 'add_stripped_text.sql'
        if not migration_file.exists():
            logger.error(f"Migration file not found: {migration_file}")
            return
        
        logger.info(f"Reading migration file: {migration_file}")
        with open(migration_file, 'r', encoding='utf-8') as f:
            migration_sql = f.read()
        
        # Execute migration
        logger.info("Running migration to add stripped_text column...")
        await conn.execute(migration_sql)
        logger.info("Migration completed successfully!")
        
        # Verify changes
        logger.info("\nVerifying migration...")
        
        stripped_text_exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'scraped_sites' AND column_name = 'stripped_text'
            )
        """)
        logger.info(f"  scraped_sites.stripped_text column: {'✓ EXISTS' if stripped_text_exists else '✗ MISSING'}")
        
        if stripped_text_exists:
            # Check if index was created
            index_exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT 1 FROM pg_indexes 
                    WHERE tablename = 'scraped_sites' AND indexname = 'idx_scraped_sites_stripped_text'
                )
            """)
            logger.info(f"  Full-text search index: {'✓ EXISTS' if index_exists else '✗ MISSING'}")
        
    except Exception as e:
        logger.error(f"Error running migration: {e}")
        import traceback
        traceback.print_exc()
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
    asyncio.run(run_migration())

