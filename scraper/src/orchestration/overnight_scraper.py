"""
Overnight Batch Scraper with Prefect Orchestration

Comprehensive scraping system with:
- Checkpoint recovery
- Parallel processing
- Security assessment
- Quality testing
- Markdown logging
"""

import asyncio
import os
import sys
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
from urllib.parse import urlparse

# Set Prefect API URL to connect to Docker server
os.environ.setdefault('PREFECT_API_URL', 'http://localhost:4200/api')

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import asyncpg
from loguru import logger

# Prefect imports - with fallback for compatibility
try:
    from prefect import flow, task
    from prefect.tasks import exponential_backoff
    PREFECT_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Prefect not available: {e}. Running in standalone mode.")
    PREFECT_AVAILABLE = False
    # Fallback decorators for testing without Prefect
    def flow(**kwargs):
        def decorator(func):
            return func
        return decorator
    
    def task(**kwargs):
        def decorator(func):
            return func
        return decorator
    
    def exponential_backoff(**kwargs):
        return [1, 2, 4]

from .checkpoint_manager import CheckpointManager
from .markdown_logger import MarkdownLogger
from .domain_boundary import DomainBoundaryChecker, load_domain_list
from ..scrapers.domain_crawler import DomainCrawler
from ..detectors.security_detector import SecurityDetector
from ..parsers.boilerplate_detector import BoilerplateDetector


# Global configuration
CONFIG_PATH = Path(__file__).parent.parent.parent / 'config' / 'scraper_config.yaml'
DOMAIN_LIST_PATH = Path(__file__).parent.parent.parent / 'config' / 'bpo_sites.txt'
MAX_RECORDS_PER_DOMAIN = 2000
PARALLEL_WORKERS = 20
QUALITY_TEST_SIZE = 10
CHECKPOINT_INTERVAL = 100  # Checkpoint every N records


def load_config() -> Dict[str, Any]:
    """Load configuration from YAML file."""
    with open(CONFIG_PATH, 'r') as f:
        return yaml.safe_load(f)


async def get_db_connection(config: Dict[str, Any]) -> asyncpg.Connection:
    """Get database connection."""
    db_host = os.getenv('POSTGRES_HOST', config['storage'].get('db_host', 'localhost'))
    db_name = os.getenv('POSTGRES_DB', config['storage'].get('db_name', 'bpo_intelligence'))
    db_user = os.getenv('POSTGRES_USER', config['storage'].get('db_user', 'bpo_user'))
    
    password_file = os.getenv('POSTGRES_PASSWORD_FILE', '/run/secrets/postgres_password')
    if os.path.exists(password_file):
        with open(password_file, 'r') as f:
            db_password = f.read().strip()
    else:
        db_password = os.getenv('POSTGRES_PASSWORD', 'bpo_secure_password_2025')
    
    return await asyncpg.connect(
        host=db_host,
        database=db_name,
        user=db_user,
        password=db_password
    )


@task(
    retries=3,
    retry_delay_seconds=exponential_backoff(backoff_factor=2),
    name="security_assessment"
)
async def security_assessment_task(domain_url: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Detect security protections and select strategy.
    
    Returns:
        Dictionary with security_type, security_level, strategy, and fingerprint
    """
    try:
        detector = SecurityDetector()
        
        # Fetch page for analysis
        from curl_cffi import requests
        response = requests.get(
            domain_url,
            timeout=30,
            impersonate="chrome110"
        )
        
        # Analyze security using detect() method
        detection_result = detector.detect(
            url=domain_url,
            status_code=response.status_code,
            headers=dict(response.headers),
            content=response.text,
            response_time=None
        )
        
        security_type = detection_result['security_type']
        security_level = detection_result['security_level']
        
        # Determine strategy based on detection results
        strategy = {
            "use_browser": detection_result['requires_browser'],
            "use_proxy": detection_result['requires_proxy'],
            "headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            } if security_level.value != "low" else {}
        }
        
        # Check if we have a strategy (we do for all detected types currently)
        has_strategy = True  # We can handle all detected security types
        
        # Create fingerprint
        fingerprint = {
            "security_type": security_type.value,
            "security_level": security_level.value,
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "indicators": detection_result['indicators'],
            "confidence": detection_result['confidence'],
            "strategy": strategy
        }
        
        return {
            "security_type": security_type.value,
            "security_level": security_level.value,
            "strategy": strategy,
            "fingerprint": fingerprint,
            "has_strategy": has_strategy
        }
        
    except Exception as e:
        logger.error(f"Security assessment failed for {domain_url}: {e}")
        return {
            "security_type": "unknown",
            "security_level": "unknown",
            "strategy": {},
            "fingerprint": {"error": str(e)},
            "has_strategy": False
        }


@task(
    retries=2,
    retry_delay_seconds=60,
    name="quality_test"
)
async def quality_test_task(
    domain_url: str,
    config: Dict[str, Any],
    db_conn: asyncpg.Connection,
    strategy: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Extract 10 sample records and assess quality.
    
    Returns:
        Dictionary with quality_ratio, sample_urls, and pass status
    """
    try:
        start_time = datetime.now()
        
        # Extract base domain
        parsed = urlparse(domain_url)
        domain = parsed.netloc.lower().replace('www.', '')
        
        # Create small test crawler
        crawler = DomainCrawler(
            config=config,
            db_connection=db_conn,
            max_depth=3,
            max_pages=QUALITY_TEST_SIZE,
            max_duration_seconds=300
        )
        
        # Run test crawl
        results = await crawler.crawl(domain_url)
        
        # Query database for quality metrics
        records = await db_conn.fetch("""
            SELECT 
                metadata,
                markdown_content
            FROM scraped_sites
            WHERE domain = $1
              AND success = true
            ORDER BY scraped_at DESC
            LIMIT $2
        """, domain, QUALITY_TEST_SIZE)
        
        if not records:
            return {
                "quality_ratio": 0.0,
                "sample_urls": [],
                "passed": False,
                "reason": "No records extracted"
            }
        
        # Calculate quality metrics
        total_html_length = 0
        total_content_length = 0
        sample_urls = []
        
        for record in records:
            metadata = record['metadata'] or {}
            if isinstance(metadata, str):
                import json
                metadata = json.loads(metadata)
            
            html_len = metadata.get('html_length', 0)
            content_len = len(record['markdown_content'] or '')
            
            total_html_length += html_len
            total_content_length += content_len
        
        # Calculate ratio
        quality_ratio = total_content_length / total_html_length if total_html_length > 0 else 0.0
        
        # Get sample URLs
        url_records = await db_conn.fetch("""
            SELECT url
            FROM scraped_sites
            WHERE domain = $1
              AND success = true
            ORDER BY scraped_at DESC
            LIMIT $2
        """, domain, QUALITY_TEST_SIZE)
        
        sample_urls = [r['url'] for r in url_records]
        
        # Decision criteria
        passed = quality_ratio >= 0.15  # At least 15% text ratio
        
        duration = (datetime.now() - start_time).total_seconds()
        
        return {
            "quality_ratio": quality_ratio,
            "sample_urls": sample_urls,
            "passed": passed,
            "records_extracted": len(records),
            "duration": duration,
            "reason": None if passed else "High HTML/Low Text Ratio"
        }
        
    except Exception as e:
        logger.error(f"Quality test failed for {domain_url}: {e}")
        return {
            "quality_ratio": 0.0,
            "sample_urls": [],
            "passed": False,
            "reason": f"Extraction: {str(e)}"
        }


@task(
    retries=3,
    retry_delay_seconds=exponential_backoff(backoff_factor=2),
    name="full_domain_scrape"
)
async def full_domain_scrape_task(
    domain_url: str,
    config: Dict[str, Any],
    db_conn: asyncpg.Connection,
    strategy: Dict[str, Any],
    checkpoint_manager: CheckpointManager
) -> Dict[str, Any]:
    """
    Extract up to 2000 records with checkpointing.
    
    Returns:
        Dictionary with records_extracted, duration, and status
    """
    try:
        start_time = datetime.now()
        
        # Extract base domain
        parsed = urlparse(domain_url)
        domain = parsed.netloc.lower().replace('www.', '')
        
        # Set in progress
        checkpoint_manager.set_in_progress(domain, 0)
        
        # Create crawler with max pages
        crawler = DomainCrawler(
            config=config,
            db_connection=db_conn,
            max_depth=5,
            max_pages=MAX_RECORDS_PER_DOMAIN,
            max_duration_seconds=7200  # 2 hours max per domain
        )
        
        # Run full crawl
        results = await crawler.crawl(domain_url)
        
        # Get actual record count from database
        record_count = await db_conn.fetchval("""
            SELECT COUNT(*)
            FROM scraped_sites
            WHERE domain = $1
              AND success = true
        """, domain)
        
        duration = (datetime.now() - start_time).total_seconds()
        
        # Mark as completed
        checkpoint_manager.mark_domain_completed(domain, record_count, "success")
        
        return {
            "records_extracted": record_count,
            "duration": duration,
            "status": "success",
            "pages_crawled": results.get('pages_crawled', 0),
            "pages_failed": results.get('pages_failed', 0)
        }
        
    except Exception as e:
        logger.error(f"Full domain scrape failed for {domain_url}: {e}")
        duration = (datetime.now() - start_time).total_seconds() if 'start_time' in locals() else 0
        
        return {
            "records_extracted": 0,
            "duration": duration,
            "status": "failed",
            "error": str(e)
        }


@flow(
    name="overnight-domain-scraper",
    persist_result=True
)
async def scrape_domains_flow(
    resume_from_checkpoint: bool = True,
    max_workers: int = PARALLEL_WORKERS
) -> Dict[str, Any]:
    """
    Main orchestration flow with checkpoint recovery.
    
    Args:
        resume_from_checkpoint: Whether to resume from checkpoint
        max_workers: Maximum parallel workers
    """
    # Initialize components
    config = load_config()
    checkpoint_manager = CheckpointManager()
    db_conn = await get_db_connection(config)
    
    try:
        # Load or create checkpoint
        if resume_from_checkpoint:
            checkpoint = checkpoint_manager.load_checkpoint()
            if checkpoint:
                logger.info(f"Resuming from checkpoint: {checkpoint['run_id']}")
                md_logger = MarkdownLogger(
                    f"logs/scrape_run_{checkpoint['run_id']}.md",
                    checkpoint['run_id']
                )
            else:
                checkpoint = checkpoint_manager.create_new_checkpoint()
                md_logger = MarkdownLogger(f"logs/scrape_run_{checkpoint['run_id']}.md")
        else:
            checkpoint = checkpoint_manager.create_new_checkpoint()
            md_logger = MarkdownLogger(f"logs/scrape_run_{checkpoint['run_id']}.md")
        
        # Load domain list
        domains = load_domain_list(str(DOMAIN_LIST_PATH))
        checkpoint['stats']['total_domains'] = len(domains)
        
        # Filter out completed domains
        completed = checkpoint.get('completed_domains', [])
        # Extract domain from URL for comparison
        completed_domains_set = {urlparse(d).netloc.lower().replace('www.', '') if isinstance(d, str) else d for d in completed}
        remaining = []
        for domain_url in domains:
            parsed = urlparse(domain_url)
            domain = parsed.netloc.lower().replace('www.', '')
            if domain not in completed_domains_set:
                remaining.append(domain_url)
        
        logger.info(f"Processing {len(remaining)} domains ({len(completed)} already completed)")
        md_logger.log_config(len(domains), max_workers, MAX_RECORDS_PER_DOMAIN)
        md_logger.start_pass(checkpoint['current_pass'])
        
        # Process domains in batches
        results = []
        for i in range(0, len(remaining), max_workers):
            batch = remaining[i:i + max_workers]
            
            logger.info(f"Processing batch {i//max_workers + 1}: {len(batch)} domains")
            
            # Process batch sequentially (Prefect ConcurrentTaskRunner handles parallelism)
            batch_results = []
            for domain_url in batch:
                try:
                    result = await process_domain_task(
                        domain_url,
                        config,
                        db_conn,
                        checkpoint_manager,
                        md_logger
                    )
                    batch_results.append(result)
                except Exception as e:
                    logger.error(f"Error processing domain {domain_url}: {e}")
                    parsed = urlparse(domain_url)
                    domain = parsed.netloc.lower().replace('www.', '')
                    batch_results.append({
                        "domain": domain,
                        "status": "marked_for_review",
                        "reason": f"Error: {str(e)}",
                        "duration": 0
                    })
            
            for result in batch_results:
                if isinstance(result, Exception):
                    logger.error(f"Domain processing error: {result}")
                else:
                    results.append(result)
        
        # Generate summary
        successful = len([r for r in results if r.get('status') == 'success'])
        successful_records = sum(r.get('records_extracted', 0) for r in results if r.get('status') == 'success')
        marked_for_review = len([r for r in results if r.get('status') == 'marked_for_review'])  
        manual_review = len([r for r in results if r.get('status') == 'manual_review'])
        total_duration = sum(r.get('duration', 0) for r in results)
        
        md_logger.log_summary(
            total_processed=len(results),
            successful=successful,
            successful_records=successful_records,
            marked_for_review=marked_for_review,
            manual_review=manual_review,
            total_duration_seconds=total_duration
        )
        
        logger.info(f"Flow completed: {successful} successful, {marked_for_review} for review, {manual_review} manual")
        
        return {
            "run_id": checkpoint['run_id'],
            "successful": successful,
            "marked_for_review": marked_for_review,
            "manual_review": manual_review,
            "total_records": successful_records
        }
        
    finally:
        await db_conn.close()


@task(name="process_domain", retries=1)
async def process_domain_task(
    domain_url: str,
    config: Dict[str, Any],
    db_conn: asyncpg.Connection,
    checkpoint_manager: CheckpointManager,
    md_logger: MarkdownLogger
) -> Dict[str, Any]:
    """Process a single domain through the full workflow."""
    start_time = datetime.now()
    
    try:
        parsed = urlparse(domain_url)
        domain = parsed.netloc.lower().replace('www.', '')
        
        # 1. Security Assessment
        security_result = await security_assessment_task(domain_url, config)
        
        if not security_result.get('has_strategy'):
            duration = (datetime.now() - start_time).total_seconds()
            reason = f"Security: {security_result.get('security_type', 'Unknown')}"
            checkpoint_manager.mark_domain_manual_review(
                domain,
                reason,
                security_result.get('fingerprint', {})
            )
            md_logger.log_domain_manual_review(
                domain,
                reason,
                security_result.get('security_type', 'Unknown'),
                security_result.get('fingerprint', {}),
                duration
            )
            return {
                "domain": domain,
                "status": "manual_review",
                "reason": reason,
                "duration": duration
            }
        
        # 2. Quality Test
        quality_result = await quality_test_task(domain_url, config, db_conn, security_result['strategy'])
        
        if not quality_result.get('passed'):
            duration = (datetime.now() - start_time).total_seconds()
            reason = quality_result.get('reason', 'Quality test failed')
            checkpoint_manager.mark_domain_for_review(domain, reason)
            md_logger.log_domain_marked_for_review(
                domain,
                reason,
                duration,
                security_result.get('security_type'),
                quality_result.get('quality_ratio'),
                quality_result.get('sample_urls')
            )
            return {
                "domain": domain,
                "status": "marked_for_review",
                "reason": reason,
                "duration": duration
            }
        
        # 3. Full Domain Scrape
        scrape_result = await full_domain_scrape_task(
            domain_url,
            config,
            db_conn,
            security_result['strategy'],
            checkpoint_manager
        )
        
        duration = (datetime.now() - start_time).total_seconds()
        
        if scrape_result.get('status') == 'success':
            md_logger.log_domain_success(
                domain,
                scrape_result.get('records_extracted', 0),
                duration,
                security_result.get('security_type'),
                quality_result.get('quality_ratio')
            )
            return {
                "domain": domain,
                "status": "success",
                "records_extracted": scrape_result.get('records_extracted', 0),
                "duration": duration
            }
        else:
            reason = scrape_result.get('error', 'Scraping failed')
            checkpoint_manager.mark_domain_for_review(domain, reason)
            md_logger.log_domain_marked_for_review(
                domain,
                reason,
                duration,
                security_result.get('security_type')
            )
            return {
                "domain": domain,
                "status": "marked_for_review",
                "reason": reason,
                "duration": duration
            }
            
    except Exception as e:
        duration = (datetime.now() - start_time).total_seconds()
        logger.error(f"Error processing domain {domain_url}: {e}")
        
        checkpoint_manager.mark_domain_for_review(domain_url, f"Error: {str(e)}")
        
        return {
            "domain": domain_url,
            "status": "marked_for_review",
            "reason": f"Error: {str(e)}",
            "duration": duration
        }


if __name__ == '__main__':
    # Configure logging
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
        level="INFO"
    )
    
    # Disable notifications for overnight run
    # (This will be handled in config)
    
    # Run flow
    asyncio.run(scrape_domains_flow(resume_from_checkpoint=True, max_workers=PARALLEL_WORKERS))

