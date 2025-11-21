#!/usr/bin/env python3
"""
Check database status and initialize if needed
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


async def check_and_init():
    """Check database and initialize if needed."""
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
        # Check existing tables
        tables = await conn.fetch("""
            SELECT tablename FROM pg_tables 
            WHERE schemaname = 'public' 
            ORDER BY tablename
        """)
        logger.info(f"\nExisting tables: {[t['tablename'] for t in tables]}")
        
        # Check if organizations table exists
        org_exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables 
                WHERE table_name = 'organizations'
            )
        """)
        
        if not org_exists:
            logger.warning("\nOrganizations table doesn't exist. Running init-db.sql...")
            init_file = Path(__file__).parent / 'init-db.sql'
            if init_file.exists():
                with open(init_file, 'r', encoding='utf-8') as f:
                    init_sql = f.read()
                await conn.execute(init_sql)
                logger.info("✓ init-db.sql executed successfully")
            else:
                logger.error(f"init-db.sql not found at {init_file}")
                return
        
        # Now run migration
        logger.info("\nRunning migration...")
        migration_file = Path(__file__).parent / 'migrations' / 'add_markdown_and_org_link.sql'
        if migration_file.exists():
            with open(migration_file, 'r', encoding='utf-8') as f:
                migration_sql = f.read()
            await conn.execute(migration_sql)
            logger.info("✓ Migration executed successfully")
        else:
            logger.error(f"Migration file not found: {migration_file}")
            return
        
        # Verify
        logger.info("\nVerifying...")
        org_uuid = await conn.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'organizations' AND column_name = 'uuid'
            )
        """)
        markdown_col = await conn.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'scraped_sites' AND column_name = 'markdown_content'
            )
        """)
        org_uuid_col = await conn.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'scraped_sites' AND column_name = 'organization_uuid'
            )
        """)
        
        logger.info(f"  organizations.uuid: {'✓' if org_uuid else '✗'}")
        logger.info(f"  scraped_sites.markdown_content: {'✓' if markdown_col else '✗'}")
        logger.info(f"  scraped_sites.organization_uuid: {'✓' if org_uuid_col else '✗'}")
        
        if org_uuid and markdown_col and org_uuid_col:
            logger.info("\n✓ All migrations completed successfully!")
        else:
            logger.warning("\n⚠ Some columns may be missing")
        
    except Exception as e:
        logger.error(f"Error: {e}")
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
    asyncio.run(check_and_init())

