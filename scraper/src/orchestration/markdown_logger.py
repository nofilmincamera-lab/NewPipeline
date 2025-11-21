"""
Markdown Logger - Structured logging for scraping runs
"""

from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
from loguru import logger


class MarkdownLogger:
    """Create structured markdown logs for scraping runs"""
    
    def __init__(self, log_file: str, checkpoint_run_id: Optional[str] = None):
        """
        Initialize markdown logger.
        
        Args:
            log_file: Path to log file
            checkpoint_run_id: Optional run ID from checkpoint
        """
        self.log_path = Path(log_file)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.run_id = checkpoint_run_id or f"scrape_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"
        self.sections: List[str] = []
        self.domain_logs: Dict[str, List[str]] = {}
        
        # Initialize log file
        self._write_header()
    
    def _write_header(self) -> None:
        """Write log file header."""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        header = f"""# Web Scraping Run - {timestamp}

## Configuration

- Run ID: `{self.run_id}`
- Log File: `{self.log_path.name}`
- Started: {timestamp}

## Execution Log

"""
        with open(self.log_path, 'w', encoding='utf-8') as f:
            f.write(header)
    
    def log_config(self, total_domains: int, parallel_workers: int, max_records: int = 2000) -> None:
        """Log configuration details."""
        config = f"""
## Configuration

- Total domains: {total_domains}
- Parallel workers: {parallel_workers}
- Max records per domain: {max_records}
- Run ID: `{self.run_id}`

"""
        self._append(config)
    
    def start_pass(self, pass_number: int) -> None:
        """Start a new pass."""
        self._append(f"\n### Pass {pass_number}: Initial Processing\n\n")
    
    def log_domain_success(
        self,
        domain: str,
        records_extracted: int,
        duration_seconds: float,
        security: Optional[str] = None,
        quality_ratio: Optional[float] = None
    ) -> None:
        """Log successful domain processing."""
        lines = [f"#### {domain} - ✅ SUCCESS\n"]
        lines.append(f"- **Records Extracted**: {records_extracted:,}")
        lines.append(f"- **Duration**: {duration_seconds:.1f}s ({duration_seconds/60:.1f}m)")
        
        if security:
            lines.append(f"- **Security**: {security}")
        if quality_ratio is not None:
            lines.append(f"- **Quality Test**: {quality_ratio*100:.1f}% text ratio (PASS)")
        
        lines.append("")
        self._append("\n".join(lines))
    
    def log_domain_marked_for_review(
        self,
        domain: str,
        reason: str,
        duration_seconds: float,
        security: Optional[str] = None,
        quality_ratio: Optional[float] = None,
        sample_urls: Optional[List[str]] = None
    ) -> None:
        """Log domain marked for review."""
        lines = [f"#### {domain} - ⚠️ MARKED_FOR_REVIEW\n"]
        lines.append(f"- **Reason**: {reason}")
        lines.append(f"- **Duration**: {duration_seconds:.1f}s")
        
        if security:
            lines.append(f"- **Security**: {security}")
        if quality_ratio is not None:
            lines.append(f"- **Quality Test**: {quality_ratio*100:.1f}% text ratio (FAIL)")
        if sample_urls:
            lines.append(f"- **Sample URLs**: {len(sample_urls)} tested")
            for url in sample_urls[:5]:
                lines.append(f"  - `{url}`")
        
        lines.append("")
        self._append("\n".join(lines))
    
    def log_domain_manual_review(
        self,
        domain: str,
        reason: str,
        protection_type: str,
        fingerprint: Dict[str, Any],
        duration_seconds: float
    ) -> None:
        """Log domain requiring manual review."""
        lines = [f"#### {domain} - 🔴 MANUAL_REVIEW\n"]
        lines.append(f"- **Reason**: {reason}")
        lines.append(f"- **Security**: {protection_type} (NO STRATEGY AVAILABLE)")
        lines.append(f"- **Duration**: {duration_seconds:.1f}s")
        lines.append("")
        lines.append("**Protection Fingerprint**:")
        lines.append("")
        
        # Format fingerprint
        for key, value in fingerprint.items():
            if isinstance(value, list):
                lines.append(f"- {key}:")
                for item in value[:10]:  # Limit to 10 items
                    lines.append(f"  - `{item}`")
            elif isinstance(value, dict):
                lines.append(f"- {key}:")
                for k, v in value.items():
                    lines.append(f"  - `{k}`: `{v}`")
            else:
                lines.append(f"- {key}: `{value}`")
        
        lines.append("")
        lines.append(f"**Action Required**: Develop custom bypass strategy")
        lines.append("")
        
        self._append("\n".join(lines))
    
    def log_summary(
        self,
        total_processed: int,
        successful: int,
        successful_records: int,
        marked_for_review: int,
        manual_review: int,
        total_duration_seconds: float
    ) -> None:
        """Log summary statistics."""
        hours = int(total_duration_seconds // 3600)
        minutes = int((total_duration_seconds % 3600) // 60)
        seconds = int(total_duration_seconds % 60)
        
        summary = f"""
## Summary Statistics

- **Total Processed**: {total_processed} domains
- **Successful**: {successful} domains ({successful_records:,} records)
- **Marked for Review**: {marked_for_review} domains
- **Manual Review Required**: {manual_review} domains
- **Total Duration**: {hours}h {minutes}m {seconds}s
- **Average per Domain**: {total_duration_seconds/total_processed:.1f}s

## Categorized Domains

### ✅ Successful Domains ({successful})

[List will be populated during execution]

### ⚠️ Marked for Review ({marked_for_review})

[List will be populated during execution]

### 🔴 Manual Review Required ({manual_review})

[List will be populated during execution]

---
*Log generated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
"""
        self._append(summary)
    
    def _append(self, content: str) -> None:
        """Append content to log file."""
        with open(self.log_path, 'a', encoding='utf-8') as f:
            f.write(content)
    
    def flush(self) -> None:
        """Ensure log is written to disk."""
        # File operations are immediately flushed, but this can be extended
        pass

