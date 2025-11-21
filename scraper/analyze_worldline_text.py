#!/usr/bin/env python3
"""
Analyze scraped text content quality from Worldline domains
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
from collections import Counter
import re

from curl_cffi import requests
from src.parsers.boilerplate_detector import BoilerplateDetector


async def fetch_page(url: str, config: dict) -> dict:
    """Fetch a page using curl_cffi."""
    try:
        proxy_url = None
        proxy_strategy = config.get('proxy_strategy', 'never')
        
        if proxy_strategy == 'always' or proxy_strategy == 'intelligent':
            # Get proxy password
            password_file = os.getenv('APIFY_PROXY_PASSWORD_FILE', '/run/secrets/apify_proxy_password')
            proxy_password = ''
            
            if os.path.exists(password_file):
                with open(password_file, 'r') as f:
                    proxy_password = f.read().strip()
            else:
                rel_path = Path(__file__).parent.parent / 'ops' / 'secrets' / 'apify_proxy_password.txt'
                if rel_path.exists():
                    with open(rel_path, 'r') as f:
                        proxy_password = f.read().strip()
                else:
                    proxy_password = os.getenv('APIFY_PROXY_PASSWORD', '')
            
            if proxy_password:
                proxy_host = config.get('apify_proxy_host', 'proxy.apify.com')
                proxy_port = config.get('apify_proxy_port', 8000)
                proxy_countries = config.get('apify_proxy_countries', ['US'])
                country = proxy_countries[0] if proxy_countries else 'US'
                proxy_url = f"http://auto:{proxy_password}@{proxy_host}:{proxy_port}?country={country}"
        
        proxies = {'http': proxy_url, 'https': proxy_url} if proxy_url else None
        
        timeout = config.get('timeout', 30)
        
        response = requests.get(
            url,
            proxies=proxies,
            timeout=timeout,
            impersonate="chrome110"
        )
        
        return {
            'success': True,
            'status_code': response.status_code,
            'content': response.text,
            'headers': dict(response.headers),
            'proxy_used': proxy_url is not None
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'status_code': None,
            'content': '',
            'proxy_used': proxy_url is not None
        }


async def analyze_text_content():
    """Analyze text content quality from Worldline scrapes."""
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
        # Get sample of Worldline URLs with good content
        logger.info("\n" + "="*80)
        logger.info("WORLDLINE TEXT CONTENT ANALYSIS")
        logger.info("="*80)
        
        # Get 10 URLs with highest content ratios
        records = await conn.fetch("""
            SELECT url, title, domain, metadata, scraped_at
            FROM scraped_sites
            WHERE domain IN ('worldline.com', 'docs.connect.worldline-solutions.com')
              AND success = true
              AND (metadata->>'main_content_length')::int > 1000
            ORDER BY (metadata->>'main_content_length')::int DESC
            LIMIT 10
        """)
        
        if not records:
            logger.warning("No Worldline records with substantial content found!")
            return
        
        logger.info(f"\nAnalyzing {len(records)} pages with highest content...\n")
        
        # Initialize detector
        boilerplate_detector = BoilerplateDetector()
        
        all_text_samples = []
        content_analysis = []
        
        for i, record in enumerate(records, 1):
            url = record['url']
            title = record['title'] or 'N/A'
            domain = record['domain']
            
            logger.info(f"{'='*80}")
            logger.info(f"Page {i}/{len(records)}: {title[:60]}")
            logger.info(f"URL: {url}")
            logger.info(f"Domain: {domain}")
            
            try:
                # Fetch the page
                fetch_result = await fetch_page(url, config)
                
                if not fetch_result['success']:
                    logger.warning(f"Failed to fetch: {fetch_result.get('error', 'Unknown error')}")
                    continue
                
                html_content = fetch_result['content']
                
                # Extract main content using boilerplate detector
                main_content = boilerplate_detector.extract_main_content(html_content)
                
                # Analyze text
                text_analysis = analyze_text(main_content, title)
                content_analysis.append({
                    'url': url,
                    'title': title,
                    'domain': domain,
                    **text_analysis
                })
                
                # Show sample
                sample_text = main_content[:500].strip()
                logger.info(f"\nContent Length: {len(main_content):,} characters")
                logger.info(f"Word Count: {text_analysis['word_count']:,} words")
                logger.info(f"Sentence Count: {text_analysis['sentence_count']} sentences")
                logger.info(f"Avg Words/Sentence: {text_analysis['avg_words_per_sentence']:.1f}")
                logger.info(f"Content Quality Score: {text_analysis['quality_score']:.1f}/10")
                
                logger.info(f"\nSample Text (first 500 chars):")
                logger.info(f"{sample_text}...")
                
                if text_analysis['top_keywords']:
                    logger.info(f"\nTop Keywords: {', '.join(text_analysis['top_keywords'][:10])}")
                
                all_text_samples.append(main_content)
                
            except Exception as e:
                logger.error(f"Error analyzing {url}: {e}")
                import traceback
                traceback.print_exc()
            
            logger.info("")
        
        # Overall summary
        logger.info("="*80)
        logger.info("OVERALL ANALYSIS SUMMARY")
        logger.info("="*80)
        
        if content_analysis:
            avg_word_count = sum(a['word_count'] for a in content_analysis) / len(content_analysis)
            avg_quality = sum(a['quality_score'] for a in content_analysis) / len(content_analysis)
            avg_sentences = sum(a['sentence_count'] for a in content_analysis) / len(content_analysis)
            
            logger.info(f"\nAverage Word Count: {avg_word_count:,.0f} words")
            logger.info(f"Average Sentence Count: {avg_sentences:,.0f} sentences")
            logger.info(f"Average Quality Score: {avg_quality:.1f}/10")
            
            # Content quality distribution
            quality_bins = {'Excellent (8-10)': 0, 'Good (6-8)': 0, 'Fair (4-6)': 0, 'Poor (<4)': 0}
            for a in content_analysis:
                score = a['quality_score']
                if score >= 8:
                    quality_bins['Excellent (8-10)'] += 1
                elif score >= 6:
                    quality_bins['Good (6-8)'] += 1
                elif score >= 4:
                    quality_bins['Fair (4-6)'] += 1
                else:
                    quality_bins['Poor (<4)'] += 1
            
            logger.info(f"\nQuality Distribution:")
            for quality, count in quality_bins.items():
                logger.info(f"  {quality}: {count} pages")
            
            # Extract common terms across all content
            all_words = []
            for text in all_text_samples:
                words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
                all_words.extend(words)
            
            word_freq = Counter(all_words)
            common_terms = [word for word, count in word_freq.most_common(20) if count >= 2]
            
            logger.info(f"\nCommon Terms Across All Pages:")
            logger.info(f"  {', '.join(common_terms[:15])}")
        
        logger.info("\n" + "="*80)
        
    finally:
        await conn.close()


def analyze_text(text: str, title: str = '') -> dict:
    """Analyze text quality and characteristics."""
    if not text or len(text.strip()) == 0:
        return {
            'word_count': 0,
            'sentence_count': 0,
            'avg_words_per_sentence': 0,
            'quality_score': 0,
            'top_keywords': []
        }
    
    # Word count
    words = re.findall(r'\b\w+\b', text)
    word_count = len(words)
    
    # Sentence count
    sentences = re.split(r'[.!?]+', text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 10]
    sentence_count = len(sentences)
    
    # Average words per sentence
    avg_words_per_sentence = word_count / sentence_count if sentence_count > 0 else 0
    
    # Quality score (0-10)
    quality_score = 0
    
    # Length score (0-3)
    if word_count >= 500:
        quality_score += 3
    elif word_count >= 200:
        quality_score += 2
    elif word_count >= 50:
        quality_score += 1
    
    # Sentence structure score (0-3)
    if avg_words_per_sentence >= 10 and avg_words_per_sentence <= 25:
        quality_score += 3
    elif avg_words_per_sentence >= 5 and avg_words_per_sentence <= 30:
        quality_score += 2
    elif sentence_count > 0:
        quality_score += 1
    
    # Content density score (0-2)
    # Check for meaningful words vs filler
    meaningful_words = [w for w in words if len(w) >= 4]
    if len(meaningful_words) / max(word_count, 1) > 0.6:
        quality_score += 2
    elif len(meaningful_words) / max(word_count, 1) > 0.4:
        quality_score += 1
    
    # Uniqueness score (0-2)
    unique_words = len(set(words))
    if unique_words / max(word_count, 1) > 0.5:
        quality_score += 2
    elif unique_words / max(word_count, 1) > 0.3:
        quality_score += 1
    
    # Top keywords (excluding common stop words)
    stop_words = {'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'her', 'was', 'one', 'our', 'out', 'day', 'get', 'has', 'him', 'his', 'how', 'its', 'may', 'new', 'now', 'old', 'see', 'two', 'who', 'way', 'use', 'has', 'had', 'may', 'but', 'use', 'can', 'will', 'with', 'this', 'that', 'from', 'they', 'have', 'been', 'said', 'each', 'which', 'their', 'time', 'will', 'about', 'would', 'there', 'could', 'other', 'after', 'first', 'never', 'these', 'think', 'where', 'being', 'under', 'know', 'over', 'much', 'should', 'before', 'right', 'while', 'during', 'without', 'those', 'both', 'such', 'through', 'around', 'against', 'among', 'between', 'within'}
    
    word_freq = Counter(w.lower() for w in words if w.lower() not in stop_words and len(w) >= 4)
    top_keywords = [word for word, count in word_freq.most_common(10)]
    
    return {
        'word_count': word_count,
        'sentence_count': sentence_count,
        'avg_words_per_sentence': avg_words_per_sentence,
        'quality_score': min(quality_score, 10),
        'top_keywords': top_keywords,
        'unique_words': unique_words,
        'meaningful_ratio': len(meaningful_words) / max(word_count, 1)
    }


if __name__ == '__main__':
    # Configure logging
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
        level="INFO"
    )
    
    # Run async main
    asyncio.run(analyze_text_content())

