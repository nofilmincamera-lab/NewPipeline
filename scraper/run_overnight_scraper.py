#!/usr/bin/env python3
"""
Run Overnight Batch Scraper

This script starts the Prefect-orchestrated overnight scraping job.
"""

import asyncio
import sys
import os
from pathlib import Path

# Set Prefect API URL to connect to Docker server
os.environ.setdefault('PREFECT_API_URL', 'http://localhost:4200/api')

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from loguru import logger
from src.orchestration.overnight_scraper import scrape_domains_flow
from src.orchestration.checkpoint_manager import CheckpointManager


async def main():
    """Main entry point."""
    # Configure logging
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
        level="INFO"
    )
    
    # Parse arguments
    resume = True
    max_workers = 20
    
    if len(sys.argv) > 1:
        if '--no-resume' in sys.argv or '--fresh' in sys.argv:
            resume = False
            logger.info("Starting fresh run (checkpoint ignored)")
        
        if '--workers' in sys.argv:
            try:
                idx = sys.argv.index('--workers')
                max_workers = int(sys.argv[idx + 1])
            except (IndexError, ValueError):
                logger.warning("Invalid --workers argument, using default: 10")
    
    # Check for existing checkpoint
    if resume:
        checkpoint_manager = CheckpointManager()
        checkpoint = checkpoint_manager.load_checkpoint()
        if checkpoint:
            logger.info(f"\n{'='*80}")
            logger.info(f"Found checkpoint: {checkpoint['run_id']}")
            logger.info(f"Completed: {len(checkpoint.get('completed_domains', []))} domains")
            logger.info(f"Marked for review: {len(checkpoint.get('marked_for_review', []))} domains")
            logger.info(f"Manual review: {len(checkpoint.get('manual_review', []))} domains")
            logger.info(f"{'='*80}\n")
            
            response = input("Resume from checkpoint? (Y/n): ").strip().lower()
            if response and response != 'y':
                logger.info("Starting fresh run")
                resume = False
                checkpoint_manager.clear_checkpoint()
        else:
            logger.info("No checkpoint found, starting fresh run")
            resume = False
    
    # Run flow
    logger.info(f"Starting overnight scraper with {max_workers} workers")
    logger.info("Press Ctrl+C to stop (checkpoint will be saved)")
    
    try:
        result = await scrape_domains_flow(
            resume_from_checkpoint=resume,
            max_workers=max_workers
        )
        
        logger.info("\n" + "="*80)
        logger.info("SCRAPING COMPLETE")
        logger.info("="*80)
        logger.info(f"Run ID: {result.get('run_id')}")
        logger.info(f"Successful: {result.get('successful')} domains")
        logger.info(f"Total Records: {result.get('total_records'):,}")
        logger.info(f"Marked for Review: {result.get('marked_for_review')} domains")
        logger.info(f"Manual Review: {result.get('manual_review')} domains")
        logger.info("="*80)
        
    except KeyboardInterrupt:
        logger.warning("\nInterrupted by user - checkpoint saved")
        logger.info("Run again with same command to resume")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())

