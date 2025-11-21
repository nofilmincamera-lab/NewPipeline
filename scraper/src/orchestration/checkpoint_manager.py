"""
Checkpoint Manager - Save/load/resume scraping state
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from loguru import logger


class CheckpointManager:
    """Manage checkpoint state for resumable scraping runs"""
    
    def __init__(self, checkpoint_dir: str = "checkpoints"):
        """
        Initialize checkpoint manager.
        
        Args:
            checkpoint_dir: Directory for checkpoint files
        """
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(exist_ok=True)
        self.checkpoint_file = self.checkpoint_dir / "scrape_checkpoint.json"
    
    def create_new_checkpoint(self, run_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a new checkpoint.
        
        Args:
            run_id: Optional run ID (generates if not provided)
            
        Returns:
            New checkpoint dictionary
        """
        if run_id is None:
            run_id = f"scrape_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"
        
        checkpoint = {
            "run_id": run_id,
            "last_updated": datetime.now().isoformat(),
            "current_pass": 1,
            "completed_domains": [],
            "marked_for_review": [],
            "manual_review": [],
            "in_progress": None,
            "stats": {
                "total_domains": 0,
                "processed": 0,
                "successful": 0,
                "total_records": 0
            }
        }
        
        self.save_checkpoint(checkpoint)
        logger.info(f"Created new checkpoint: {run_id}")
        return checkpoint
    
    def load_checkpoint(self) -> Optional[Dict[str, Any]]:
        """
        Load existing checkpoint if available and recent (< 24 hours).
        
        Returns:
            Checkpoint dictionary or None if not available/expired
        """
        if not self.checkpoint_file.exists():
            return None
        
        try:
            with open(self.checkpoint_file, 'r') as f:
                checkpoint = json.load(f)
            
            # Check if checkpoint is less than 24 hours old
            last_updated = datetime.fromisoformat(checkpoint['last_updated'])
            age = datetime.now() - last_updated
            
            if age > timedelta(hours=24):
                logger.warning(f"Checkpoint expired (age: {age})")
                return None
            
            logger.info(f"Loaded checkpoint: {checkpoint['run_id']} (age: {age})")
            return checkpoint
            
        except Exception as e:
            logger.error(f"Error loading checkpoint: {e}")
            return None
    
    def save_checkpoint(self, checkpoint: Dict[str, Any]) -> None:
        """
        Save checkpoint to disk.
        
        Args:
            checkpoint: Checkpoint dictionary
        """
        try:
            checkpoint['last_updated'] = datetime.now().isoformat()
            with open(self.checkpoint_file, 'w') as f:
                json.dump(checkpoint, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving checkpoint: {e}")
    
    def mark_domain_completed(
        self, 
        domain: str, 
        records_extracted: int = 0,
        status: str = "success"
    ) -> None:
        """Mark a domain as completed."""
        checkpoint = self.load_checkpoint()
        if not checkpoint:
            checkpoint = self.create_new_checkpoint()
        
        # Extract domain name from URL if needed
        from urllib.parse import urlparse
        if '://' in domain:
            parsed = urlparse(domain)
            domain_name = parsed.netloc.lower().replace('www.', '')
        else:
            domain_name = domain
        
        # Check if already completed
        completed = checkpoint.get('completed_domains', [])
        completed_domains_set = {urlparse(d).netloc.lower().replace('www.', '') if '://' in str(d) else str(d) for d in completed}
        
        if domain_name in completed_domains_set:
            return
        
        checkpoint['completed_domains'].append(domain_name)
        
        # Remove from in_progress if present
        in_progress = checkpoint.get('in_progress')
        if in_progress and isinstance(in_progress, dict) and in_progress.get('domain') == domain_name:
            checkpoint['in_progress'] = None
        
        # Update stats
        checkpoint['stats']['processed'] += 1
        checkpoint['stats']['successful'] += 1
        checkpoint['stats']['total_records'] += records_extracted
        
        self.save_checkpoint(checkpoint)
    
    def mark_domain_for_review(self, domain: str, reason: str) -> None:
        """Mark a domain for review."""
        checkpoint = self.load_checkpoint() or self.create_new_checkpoint()
        
        if domain not in checkpoint['marked_for_review']:
            checkpoint['marked_for_review'].append({
                "domain": domain,
                "reason": reason,
                "timestamp": datetime.now().isoformat()
            })
            checkpoint['stats']['processed'] += 1
            self.save_checkpoint(checkpoint)
    
    def mark_domain_manual_review(self, domain: str, reason: str, details: Dict[str, Any]) -> None:
        """Mark a domain for manual review."""
        checkpoint = self.load_checkpoint() or self.create_new_checkpoint()
        
        if domain not in checkpoint['manual_review']:
            checkpoint['manual_review'].append({
                "domain": domain,
                "reason": reason,
                "details": details,
                "timestamp": datetime.now().isoformat()
            })
            checkpoint['stats']['processed'] += 1
            self.save_checkpoint(checkpoint)
    
    def set_in_progress(self, domain: str, records_extracted: int = 0) -> None:
        """Set a domain as in progress."""
        checkpoint = self.load_checkpoint() or self.create_new_checkpoint()
        
        checkpoint['in_progress'] = {
            "domain": domain,
            "records_extracted": records_extracted,
            "started_at": datetime.now().isoformat()
        }
        
        self.save_checkpoint(checkpoint)
    
    def clear_checkpoint(self) -> None:
        """Clear the checkpoint file."""
        if self.checkpoint_file.exists():
            self.checkpoint_file.unlink()
            logger.info("Checkpoint cleared")

