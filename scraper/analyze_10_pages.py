#!/usr/bin/env python3
"""
Analyze the 10 pages scraped from Worldline domains
"""

import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))

import yaml
import asyncpg
from loguru import logger
import json
import re
from collections import Counter

async def analyze_recent_pages():
    """Analyze the 10 most recently scraped pages from Worldline."""
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
        # Get the 10 most recently scraped pages from Worldline (last 5 minutes)
        cutoff_time = datetime.now() - timedelta(minutes=5)
        
        logger.info("\n" + "="*80)
        logger.info("ANALYZING 10 RECENT WORLDLINE PAGES")
        logger.info("="*80)
        
        records = await conn.fetch("""
            SELECT 
                url, 
                title, 
                domain, 
                metadata,
                scraped_at,
                status_code,
                success,
                response_time,
                markdown_content,
                stripped_text
            FROM scraped_sites
            WHERE domain IN ('worldline.com', 'docs.connect.worldline-solutions.com')
              AND scraped_at >= $1
              AND success = true
            ORDER BY scraped_at DESC
            LIMIT 20
        """, cutoff_time)
        
        if not records or len(records) < 10:
            logger.warning("Not enough recent records found! Trying all recent records...")
            records = await conn.fetch("""
                SELECT 
                    url, 
                    title, 
                    domain, 
                    metadata,
                    scraped_at,
                    status_code,
                    success,
                    response_time,
                    markdown_content
                FROM scraped_sites
                WHERE domain IN ('worldline.com', 'docs.connect.worldline-solutions.com')
                  AND success = true
                ORDER BY scraped_at DESC
                LIMIT 20
            """)
        
        # Take the 10 most recent
        records = records[:10]
        
        if not records:
            logger.error("No Worldline records found in database!")
            return
        
        logger.info(f"\nFound {len(records)} pages to analyze\n")
        
        # Analyze each page
        page_analyses = []
        all_keywords = []
        
        for i, record in enumerate(records, 1):
            url = record['url']
            title = record['title'] or 'N/A'
            domain = record['domain']
            metadata = record['metadata']
            scraped_at = record['scraped_at']
            status_code = record['status_code']
            response_time = record['response_time']
            markdown_content = record.get('markdown_content')
            stripped_text = record.get('stripped_text')
            
            logger.info("="*80)
            logger.info(f"PAGE {i}/{len(records)}")
            logger.info("="*80)
            logger.info(f"URL: {url}")
            logger.info(f"Title: {title}")
            logger.info(f"Domain: {domain}")
            logger.info(f"Status: {status_code} | Response Time: {response_time:.2f}s" if response_time else f"Status: {status_code}")
            logger.info(f"Scraped: {scraped_at}")
            
            # Parse metadata
            html_length = 0
            markdown_length = 0
            content_length = 0
            boilerplate_ratio = 0
            
            if metadata:
                try:
                    if isinstance(metadata, str):
                        meta = json.loads(metadata)
                    else:
                        meta = metadata
                    
                    html_length = meta.get('html_length', 0)
                    markdown_length = meta.get('markdown_length', 0)
                    content_length = meta.get('main_content_length', 0)
                    boilerplate_ratio = meta.get('boilerplate_ratio', 0)
                    
                except Exception as e:
                    logger.warning(f"  Could not parse metadata: {e}")
            
            # Check markdown_content and stripped_text if available
            if markdown_content:
                markdown_length = len(markdown_content)
            
            # Use stripped_text length for content_length if available
            if stripped_text:
                stripped_length = len(stripped_text)
                content_length = stripped_length
            elif markdown_content:
                content_length = len(markdown_content)
            else:
                content_length = 0
            
            logger.info(f"\nContent Metrics:")
            logger.info(f"  HTML Length: {html_length:,} chars")
            if stripped_text:
                logger.info(f"  Stripped Text Length: {len(stripped_text):,} chars")
            logger.info(f"  Markdown Length: {markdown_length:,} chars")
            logger.info(f"  Main Content: {content_length:,} chars")
            if boilerplate_ratio:
                logger.info(f"  Boilerplate Ratio: {boilerplate_ratio:.2%}")
            
            # Calculate size reduction
            if html_length > 0 and stripped_text:
                reduction = (1 - len(stripped_text) / html_length) * 100
                logger.info(f"  Size Reduction: {reduction:.1f}% (HTML → Stripped Text)")
            
            # Determine if page was skipped
            if content_length == 0:
                logger.warning(f"  ⚠️  Page was SKIPPED (likely due to boilerplate detection)")
            else:
                logger.info(f"  ✓ Page content extracted successfully")
            
            # Estimate word count from content length
            estimated_words = content_length // 5  # Rough estimate: 5 chars per word
            logger.info(f"  Estimated Words: ~{estimated_words:,}")
            
            # Show stripped text preview if available (preferred over markdown)
            if stripped_text and len(stripped_text) > 0:
                preview = stripped_text[:300].strip()
                if len(stripped_text) > 300:
                    preview += "..."
                logger.info(f"\n  Stripped Text Preview (first 300 chars):")
                logger.info(f"  {preview}")
            elif markdown_content and len(markdown_content) > 0:
                preview = markdown_content[:300].strip()
                if len(markdown_content) > 300:
                    preview += "..."
                logger.info(f"\n  Markdown Preview (first 300 chars):")
                logger.info(f"  {preview}")
            
            page_analyses.append({
                'url': url,
                'title': title,
                'domain': domain,
                'html_length': html_length,
                'markdown_length': markdown_length,
                'stripped_text_length': len(stripped_text) if stripped_text else 0,
                'content_length': content_length,
                'boilerplate_ratio': boilerplate_ratio,
                'estimated_words': estimated_words,
                'response_time': response_time,
                'was_skipped': content_length == 0
            })
            
            # Extract keywords from title and URL
            text_to_analyze = f"{title} {url}".lower()
            words = re.findall(r'\b[a-zA-Z]{4,}\b', text_to_analyze)
            all_keywords.extend(words)
            
            logger.info("")
        
        # Summary statistics
        logger.info("="*80)
        logger.info("SUMMARY STATISTICS")
        logger.info("="*80)
        
        if page_analyses:
            total_html = sum(p['html_length'] for p in page_analyses)
            total_markdown = sum(p['markdown_length'] for p in page_analyses)
            total_stripped = sum(p['stripped_text_length'] for p in page_analyses)
            total_content = sum(p['content_length'] for p in page_analyses)
            total_words = sum(p['estimated_words'] for p in page_analyses)
            avg_response_time = sum(p['response_time'] for p in page_analyses if p['response_time']) / len([p for p in page_analyses if p['response_time']])
            
            avg_html = total_html / len(page_analyses)
            avg_markdown = total_markdown / len(page_analyses)
            avg_stripped = total_stripped / len(page_analyses)
            avg_content = total_content / len(page_analyses)
            avg_words = total_words / len(page_analyses)
            
            logger.info(f"\nTotal Pages Analyzed: {len(page_analyses)}")
            logger.info(f"\nContent Totals:")
            logger.info(f"  Total HTML: {total_html:,} chars")
            logger.info(f"  Total Stripped Text: {total_stripped:,} chars")
            logger.info(f"  Total Markdown: {total_markdown:,} chars")
            logger.info(f"  Total Main Content: {total_content:,} chars")
            logger.info(f"  Total Estimated Words: {total_words:,}")
            
            # Calculate overall size reduction
            if total_html > 0:
                overall_reduction = (1 - total_stripped / total_html) * 100
                logger.info(f"  Overall Size Reduction: {overall_reduction:.1f}% (HTML → Stripped Text)")
            
            logger.info(f"\nAverages per Page:")
            logger.info(f"  Avg HTML: {avg_html:,.0f} chars")
            logger.info(f"  Avg Stripped Text: {avg_stripped:,.0f} chars")
            logger.info(f"  Avg Markdown: {avg_markdown:,.0f} chars")
            logger.info(f"  Avg Main Content: {avg_content:,.0f} chars")
            logger.info(f"  Avg Words: {avg_words:,.0f}")
            logger.info(f"  Avg Response Time: {avg_response_time:.2f}s")
            
            # Domain breakdown
            worldline_pages = [p for p in page_analyses if p['domain'] == 'worldline.com']
            docs_pages = [p for p in page_analyses if p['domain'] == 'docs.connect.worldline-solutions.com']
            
            logger.info(f"\nDomain Breakdown:")
            logger.info(f"  worldline.com: {len(worldline_pages)} pages")
            if worldline_pages:
                logger.info(f"    Avg Content: {sum(p['content_length'] for p in worldline_pages) / len(worldline_pages):,.0f} chars")
            logger.info(f"  docs.connect.worldline-solutions.com: {len(docs_pages)} pages")
            if docs_pages:
                logger.info(f"    Avg Content: {sum(p['content_length'] for p in docs_pages) / len(docs_pages):,.0f} chars")
            
            # Content quality distribution
            high_content = len([p for p in page_analyses if p['content_length'] > 5000])
            medium_content = len([p for p in page_analyses if 1000 <= p['content_length'] <= 5000])
            low_content = len([p for p in page_analyses if 0 < p['content_length'] < 1000])
            skipped = len([p for p in page_analyses if p['was_skipped']])
            
            logger.info(f"\nContent Quality Distribution:")
            logger.info(f"  High Content (>5K chars): {high_content} pages")
            logger.info(f"  Medium Content (1K-5K chars): {medium_content} pages")
            logger.info(f"  Low Content (<1K chars): {low_content} pages")
            logger.info(f"  Skipped (0 content): {skipped} pages")
            
            # Top keywords
            if all_keywords:
                keyword_freq = Counter(all_keywords)
                top_keywords = [word for word, count in keyword_freq.most_common(15)]
                logger.info(f"\nTop Keywords (from titles/URLs):")
                logger.info(f"  {', '.join(top_keywords)}")
            
            # Page types
            logger.info(f"\nPage Types Identified:")
            page_types = {
                'home': len([p for p in page_analyses if '/home' in p['url'] or p['url'].endswith('/')]),
                'documentation': len([p for p in page_analyses if 'docs' in p['url'] or 'documentation' in p['url']]),
                'solutions': len([p for p in page_analyses if 'solution' in p['url'].lower()]),
                'navigation': len([p for p in page_analyses if 'navigation' in p['url'].lower()]),
                'other': len([p for p in page_analyses if not any(x in p['url'].lower() for x in ['home', 'docs', 'solution', 'navigation'])])
            }
            for page_type, count in page_types.items():
                if count > 0:
                    logger.info(f"  {page_type.capitalize()}: {count} pages")
        
        logger.info("\n" + "="*80)
        logger.info("ANALYSIS COMPLETE")
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
    asyncio.run(analyze_recent_pages())

