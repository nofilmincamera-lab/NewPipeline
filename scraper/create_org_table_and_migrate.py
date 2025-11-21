#!/usr/bin/env python3
"""
Create organizations table if missing and run migration
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


async def setup_database():
    """Create organizations table and run migration."""
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
        # Enable UUID extension
        await conn.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";")
        logger.info("✓ UUID extension enabled")
        
        # Create organizations table if it doesn't exist
        org_table_sql = """
        CREATE TABLE IF NOT EXISTS organizations (
            id SERIAL PRIMARY KEY,
            canonical_name VARCHAR(255),
            domain VARCHAR(255) UNIQUE NOT NULL,
            aliases JSONB DEFAULT '[]'::jsonb,
            organizational_type VARCHAR(100),
            organizational_classification VARCHAR(255),
            customer_segment VARCHAR(10) CHECK (customer_segment IN ('B2B', 'B2C', 'Both', NULL)),
            founded_year INTEGER,
            headquarters_country VARCHAR(100),
            employee_count_range VARCHAR(50),
            auto_created BOOLEAN DEFAULT false,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
        await conn.execute(org_table_sql)
        logger.info("✓ Organizations table created/verified")
        
        # Create indexes
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_organizations_domain ON organizations(domain);
            CREATE INDEX IF NOT EXISTS idx_organizations_canonical_name ON organizations(canonical_name);
        """)
        
        # Now run migration to add UUID and other columns
        logger.info("\nRunning migration...")
        
        # Add UUID to organizations
        await conn.execute("""
            DO $$ 
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name = 'organizations' AND column_name = 'uuid'
                ) THEN
                    ALTER TABLE organizations ADD COLUMN uuid UUID DEFAULT uuid_generate_v4() UNIQUE;
                    CREATE INDEX IF NOT EXISTS idx_organizations_uuid ON organizations(uuid);
                END IF;
            END $$;
        """)
        logger.info("✓ Added UUID to organizations")
        
        # Populate UUIDs for existing organizations
        await conn.execute("UPDATE organizations SET uuid = uuid_generate_v4() WHERE uuid IS NULL;")
        
        # Add markdown_content to scraped_sites
        await conn.execute("""
            DO $$ 
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name = 'scraped_sites' AND column_name = 'markdown_content'
                ) THEN
                    ALTER TABLE scraped_sites ADD COLUMN markdown_content TEXT;
                END IF;
            END $$;
        """)
        logger.info("✓ Added markdown_content to scraped_sites")
        
        # Add organization_uuid to scraped_sites
        await conn.execute("""
            DO $$ 
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name = 'scraped_sites' AND column_name = 'organization_uuid'
                ) THEN
                    ALTER TABLE scraped_sites ADD COLUMN organization_uuid UUID REFERENCES organizations(uuid) ON DELETE SET NULL;
                    CREATE INDEX IF NOT EXISTS idx_scraped_sites_org_uuid ON scraped_sites(organization_uuid);
                END IF;
            END $$;
        """)
        logger.info("✓ Added organization_uuid to scraped_sites")
        
        # Link existing scraped_sites to organizations by domain
        await conn.execute("""
            UPDATE scraped_sites ss
            SET organization_uuid = o.uuid
            FROM organizations o
            WHERE ss.domain = o.domain
              AND ss.organization_uuid IS NULL;
        """)
        logger.info("✓ Linked existing records to organizations")
        
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
    asyncio.run(setup_database())

