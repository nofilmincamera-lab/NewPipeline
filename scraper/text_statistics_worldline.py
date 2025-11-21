#!/usr/bin/env python3
"""
Analyze text statistics from Worldline scraped content
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


async def analyze_text_statistics():
    """Analyze text statistics from Worldline scrapes."""
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
        # Get Worldline records with markdown content
        logger.info("\n" + "="*80)
        logger.info("WORLDLINE TEXT STATISTICS")
        logger.info("="*80)
        
        records = await conn.fetch("""
            SELECT 
                ss.url, 
                ss.title, 
                ss.domain, 
                ss.markdown_content,
                ss.organization_uuid,
                ss.metadata,
                ss.scraped_at,
                o.canonical_name as org_name
            FROM scraped_sites ss
            LEFT JOIN organizations o ON ss.organization_uuid = o.uuid
            WHERE ss.domain IN ('worldline.com', 'docs.connect.worldline-solutions.com')
              AND ss.success = true
              AND ss.markdown_content IS NOT NULL
              AND LENGTH(ss.markdown_content) > 100
            ORDER BY ss.scraped_at DESC
        """)
        
        if not records:
            logger.warning("No Worldline records with markdown content found!")
            logger.info("\nMake sure you've:")
            logger.info("1. Run the migration: migrations/add_markdown_and_org_link.sql")
            logger.info("2. Scraped some pages with the new code")
            return
        
        logger.info(f"\nFound {len(records)} records with markdown content\n")
        
        # Statistics
        total_chars = 0
        total_words = 0
        total_sentences = 0
        all_words = []
        records_with_stats = []
        
        for record in records:
            markdown = record['markdown_content'] or ''
            
            # Basic stats
            char_count = len(markdown)
            word_count = len(re.findall(r'\b\w+\b', markdown))
            sentences = re.split(r'[.!?]+', markdown)
            sentences = [s.strip() for s in sentences if len(s.strip()) > 10]
            sentence_count = len(sentences)
            
            # Extract words for common terms
            words = re.findall(r'\b[a-zA-Z]{3,}\b', markdown.lower())
            all_words.extend(words)
            
            # Store stats
            stats = {
                'url': record['url'],
                'title': record['title'],
                'domain': record['domain'],
                'chars': char_count,
                'words': word_count,
                'sentences': sentence_count,
                'org_uuid': str(record['organization_uuid']) if record['organization_uuid'] else None,
                'org_name': record['org_name']
            }
            records_with_stats.append(stats)
            
            total_chars += char_count
            total_words += word_count
            total_sentences += sentence_count
        
        # Print statistics
        logger.info("="*80)
        logger.info("OVERALL STATISTICS")
        logger.info("="*80)
        logger.info(f"Total Records: {len(records)}")
        logger.info(f"Total Characters: {total_chars:,}")
        logger.info(f"Total Words: {total_words:,}")
        logger.info(f"Total Sentences: {total_sentences:,}")
        logger.info(f"Average Characters per Record: {total_chars // len(records):,}")
        logger.info(f"Average Words per Record: {total_words // len(records):,}")
        logger.info(f"Average Sentences per Record: {total_sentences // len(records):,}")
        logger.info(f"Average Words per Sentence: {total_words / total_sentences:.1f}" if total_sentences > 0 else "Average Words per Sentence: N/A")
        
        # Common terms
        word_freq = Counter(all_words)
        common_terms = word_freq.most_common(20)
        
        logger.info("\n" + "="*80)
        logger.info("TOP 20 COMMON TERMS")
        logger.info("="*80)
        for term, count in common_terms:
            logger.info(f"  {term}: {count}")
        
        # Domain breakdown
        logger.info("\n" + "="*80)
        logger.info("DOMAIN BREAKDOWN")
        logger.info("="*80)
        
        domain_stats = {}
        for stats in records_with_stats:
            domain = stats['domain']
            if domain not in domain_stats:
                domain_stats[domain] = {
                    'count': 0,
                    'chars': 0,
                    'words': 0,
                    'sentences': 0
                }
            domain_stats[domain]['count'] += 1
            domain_stats[domain]['chars'] += stats['chars']
            domain_stats[domain]['words'] += stats['words']
            domain_stats[domain]['sentences'] += stats['sentences']
        
        for domain, stats in domain_stats.items():
            logger.info(f"\n{domain}:")
            logger.info(f"  Records: {stats['count']}")
            logger.info(f"  Total Characters: {stats['chars']:,}")
            logger.info(f"  Total Words: {stats['words']:,}")
            logger.info(f"  Average Words per Record: {stats['words'] // stats['count']:,}")
        
        # Organization linking
        logger.info("\n" + "="*80)
        logger.info("ORGANIZATION LINKING")
        logger.info("="*80)
        
        linked_count = sum(1 for s in records_with_stats if s['org_uuid'])
        logger.info(f"Records linked to organizations: {linked_count}/{len(records_with_stats)} ({linked_count/len(records_with_stats)*100:.1f}%)")
        
        # Sample records
        logger.info("\n" + "="*80)
        logger.info("SAMPLE RECORDS (Top 5 by word count)")
        logger.info("="*80)
        
        top_records = sorted(records_with_stats, key=lambda x: x['words'], reverse=True)[:5]
        for i, stats in enumerate(top_records, 1):
            logger.info(f"\n{i}. {stats['title'][:60]}")
            logger.info(f"   URL: {stats['url'][:70]}")
            logger.info(f"   Domain: {stats['domain']}")
            logger.info(f"   Words: {stats['words']:,} | Sentences: {stats['sentences']}")
            logger.info(f"   Org: {stats['org_name'] or 'Not linked'} (UUID: {stats['org_uuid'] or 'N/A'})")
        
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
    asyncio.run(analyze_text_statistics())

