#!/usr/bin/env python3
"""
Test Core Overnight Scraper Components (without Prefect)

This tests all components except the Prefect flow orchestration
"""

import sys
import asyncio
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from orchestration.checkpoint_manager import CheckpointManager
from orchestration.markdown_logger import MarkdownLogger
from orchestration.domain_boundary import DomainBoundaryChecker, load_domain_list

# Try to import config loader (doesn't require Prefect)
try:
    import sys
    import os
    import yaml
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent))
    
    def load_config():
        config_path = Path(__file__).parent / 'config' / 'scraper_config.yaml'
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    
    def test_config_loading():
        """Test configuration loading."""
        try:
            config = load_config()
            return config is not None and 'storage' in config
        except:
            return False
except:
    load_config = None
    test_config_loading = lambda: False


async def test_checkpoint():
    """Test checkpoint manager."""
    print("\n[TEST] Checkpoint Manager")
    print("-" * 60)
    try:
        cm = CheckpointManager()
        checkpoint = cm.create_new_checkpoint("test_run")
        
        assert checkpoint['run_id'] == "test_run"
        print("[OK] Checkpoint created")
        
        loaded = cm.load_checkpoint()
        assert loaded['run_id'] == "test_run"
        print("[OK] Checkpoint loaded")
        
        cm.mark_domain_completed("example.com", 100)
        loaded = cm.load_checkpoint()
        assert "example.com" in loaded['completed_domains']
        print("[OK] Domain marked completed")
        
        cm.mark_domain_for_review("review.com", "Low quality")
        loaded = cm.load_checkpoint()
        assert len(loaded['marked_for_review']) > 0
        print("[OK] Domain marked for review")
        
        cm.clear_checkpoint()
        print("[OK] Checkpoint cleared")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        import traceback
        traceback.print_exc()
        return False


def test_markdown_logger():
    """Test markdown logger."""
    print("\n[TEST] Markdown Logger")
    print("-" * 60)
    try:
        logger = MarkdownLogger("logs/test_log.md", "test_run")
        logger.log_config(73, 10, 2000)
        logger.start_pass(1)
        logger.log_domain_success("example.com", 1500, 120.5, "Cloudflare", 0.25)
        logger.log_domain_marked_for_review("review.com", "Low quality", 45.2, quality_ratio=0.08)
        logger.log_summary(2, 1, 1500, 1, 0, 165.7)
        
        # Check file exists
        log_file = Path("logs/test_log.md")
        assert log_file.exists()
        print("[OK] Log file created")
        
        content = log_file.read_text(encoding='utf-8')
        assert "example.com" in content
        assert "SUCCESS" in content
        print("[OK] Log content written")
        
        # Cleanup
        log_file.unlink()
        print("[OK] Test log cleaned up")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        import traceback
        traceback.print_exc()
        return False


def test_domain_boundary():
    """Test domain boundary checker."""
    print("\n[TEST] Domain Boundary Checker")
    print("-" * 60)
    try:
        checker = DomainBoundaryChecker("worldline.com")
        
        # Test exact match
        assert checker.is_within_boundary("https://worldline.com/page")
        print("[OK] Exact domain match")
        
        # Test subdomain
        assert checker.is_within_boundary("https://blog.worldline.com/page")
        print("[OK] Subdomain allowed")
        
        # Test derivative
        assert checker.is_within_boundary("https://worldline-solutions.com/page")
        print("[OK] Derivative domain allowed")
        
        # Test file download
        assert checker.is_within_boundary("https://external.com/document.pdf")
        print("[OK] File downloads allowed")
        
        # Test out of boundary
        assert not checker.is_within_boundary("https://completely-different.com/page")
        print("[OK] Out-of-boundary rejected")
        
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        import traceback
        traceback.print_exc()
        return False


def test_domain_list():
    """Test domain list loading."""
    print("\n[TEST] Domain List Loader")
    print("-" * 60)
    try:
        domains = load_domain_list('config/bpo_sites.txt')
        
        assert len(domains) > 0
        print(f"[OK] Loaded {len(domains)} domains")
        
        # Check format
        assert domains[0].startswith('http')
        print("[OK] URLs properly formatted")
        
        # Check no comments
        comment_count = sum(1 for d in domains if d.startswith('#'))
        assert comment_count == 0
        print("[OK] Comments filtered out")
        
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        import traceback
        traceback.print_exc()
        return False


def test_config():
    """Test configuration loading."""
    print("\n[TEST] Configuration")
    print("-" * 60)
    try:
        if load_config is None:
            print("[SKIP] Config loader not available")
            return True
        
        config = load_config()
        
        assert 'storage' in config
        assert 'proxy_strategy' in config
        print("[OK] Config loaded")
        
        # Don't test DB connection here (requires Prefect components)
        print("[SKIP] Database connection test (requires Prefect)")
        
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("=" * 80)
    print("Overnight Scraper Core Components Test")
    print("=" * 80)
    
    results = []
    results.append(asyncio.run(test_checkpoint()))
    results.append(test_markdown_logger())
    results.append(test_domain_boundary())
    results.append(test_domain_list())
    results.append(test_config())
    
    passed = sum(results)
    total = len(results)
    
    print("\n" + "=" * 80)
    print(f"Results: {passed}/{total} tests passed")
    if passed == total:
        print("[SUCCESS] All core components working!")
        print("\nNext step: Install Prefect 3.1.9 with: pip install prefect==3.1.9")
        print("           Then run: python run_overnight_scraper.py")
    else:
        print("[WARNING] Some tests failed. Review errors above.")
    print("=" * 80)


if __name__ == '__main__':
    # Ensure directories exist
    Path("logs").mkdir(exist_ok=True)
    Path("checkpoints").mkdir(exist_ok=True)
    
    main()

