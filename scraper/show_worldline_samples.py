#!/usr/bin/env python3
"""
Show sample Worldline scraped records with markdown content
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
import re
from collections import Counter


async def show_samples():
    """Show sample Worldline records with markdown content."""
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
        # Get sample Worldline records with markdown content
        logger.info("\n" + "="*80)
        logger.info("WORLDLINE SAMPLE RECORDS")
        logger.info("="*80)
        
        # Get top 5 records by word count
        records = await conn.fetch("""
            SELECT 
                ss.url, 
                ss.title, 
                ss.domain, 
                ss.markdown_content,
                ss.organization_uuid,
                ss.metadata,
                ss.scraped_at,
                ss.status_code,
                ss.success,
                o.canonical_name as org_name,
                o.uuid as org_uuid
            FROM scraped_sites ss
            LEFT JOIN organizations o ON ss.organization_uuid = o.uuid
            WHERE ss.domain IN ('worldline.com', 'docs.connect.worldline-solutions.com')
              AND ss.success = true
              AND ss.markdown_content IS NOT NULL
              AND LENGTH(ss.markdown_content) > 500
            ORDER BY LENGTH(ss.markdown_content) DESC
            LIMIT 5
        """)
        
        if not records:
            logger.warning("No Worldline records with substantial markdown content found!")
            return
        
        logger.info(f"\nShowing {len(records)} sample records:\n")
        
        for i, record in enumerate(records, 1):
            logger.info("="*80)
            logger.info(f"RECORD {i}/{len(records)}")
            logger.info("="*80)
            
            # Basic info
            logger.info(f"URL: {record['url']}")
            logger.info(f"Title: {record['title']}")
            logger.info(f"Domain: {record['domain']}")
            logger.info(f"Status: {record['status_code']} {'✓' if record['success'] else '✗'}")
            logger.info(f"Scraped: {record['scraped_at']}")
            
            # Organization info
            org_uuid = str(record['organization_uuid']) if record['organization_uuid'] else None
            org_name = record['org_name'] or 'Not set'
            logger.info(f"Organization: {org_name} (UUID: {org_uuid})")
            
            # Metadata
            if record['metadata']:
                try:
                    meta = json.loads(record['metadata']) if isinstance(record['metadata'], str) else record['metadata']
                    logger.info(f"HTML Length: {meta.get('html_length', 0):,} chars")
                    logger.info(f"Markdown Length: {meta.get('markdown_length', 0):,} chars")
                    logger.info(f"Content Length: {meta.get('main_content_length', 0):,} chars")
                except:
                    pass
            
            # Markdown content preview
            markdown = record['markdown_content'] or ''
            if markdown:
                word_count = len(re.findall(r'\b\w+\b', markdown))
                char_count = len(markdown)
                sentence_count = len(re.split(r'[.!?]+', markdown.strip()))
                
                logger.info(f"\nContent Statistics:")
                logger.info(f"  Characters: {char_count:,}")
                logger.info(f"  Words: {word_count:,}")
                logger.info(f"  Sentences: ~{sentence_count}")
                
                # Show first 1000 characters of markdown
                preview = markdown[:1000].strip()
                if len(markdown) > 1000:
                    preview += "\n... [truncated]"
                
                logger.info(f"\nMarkdown Preview (first 1000 chars):")
                logger.info("-"*80)
                logger.info(preview)
                logger.info("-"*80)
                
                # Extract first few sentences for better readability
                sentences = re.split(r'([.!?]+)', markdown)
                first_sentences = []
                current_sentence = ""
                for part in sentences[:10]:
                    current_sentence += part
                    if part.strip() and part.strip() in '.!?':
                        first_sentences.append(current_sentence.strip())
                        current_sentence = ""
                        if len(first_sentences) >= 3:
                            break
                
                if first_sentences:
                    logger.info(f"\nFirst Few Sentences:")
                    for sent in first_sentences[:3]:
                        if sent and len(sent) > 20:
                            logger.info(f"  • {sent[:200]}{'...' if len(sent) > 200 else ''}")
            else:
                logger.warning("  No markdown content available")
            
            logger.info("")
        
        logger.info("="*80)
        logger.info("SUMMARY")
        logger.info("="*80)
        total_chars = sum(len(r['markdown_content'] or '') for r in records)
        total_words = sum(len(re.findall(r'\b\w+\b', r['markdown_content'] or '')) for r in records)
        
        logger.info(f"Total Records Shown: {len(records)}")
        logger.info(f"Total Characters: {total_chars:,}")
        logger.info(f"Total Words: {total_words:,}")
        logger.info(f"Average Characters per Record: {total_chars // len(records):,}")
        logger.info(f"Average Words per Record: {total_words // len(records):,}")
        logger.info("="*80)
        
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
    asyncio.run(show_samples())

