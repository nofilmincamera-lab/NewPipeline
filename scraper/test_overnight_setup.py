#!/usr/bin/env python3
"""
Quick test to verify overnight scraper setup
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

def test_imports():
    """Test that all modules can be imported."""
    print("Testing imports...")
    
    try:
        from orchestration.checkpoint_manager import CheckpointManager
        print("[OK] CheckpointManager")
    except Exception as e:
        print(f"[FAIL] CheckpointManager: {e}")
        return False
    
    try:
        from orchestration.markdown_logger import MarkdownLogger
        print("[OK] MarkdownLogger")
    except Exception as e:
        print(f"[FAIL] MarkdownLogger: {e}")
        return False
    
    try:
        from orchestration.domain_boundary import DomainBoundaryChecker, load_domain_list
        print("[OK] DomainBoundaryChecker")
    except Exception as e:
        print(f"[FAIL] DomainBoundaryChecker: {e}")
        return False
    
    try:
        from orchestration.overnight_scraper import scrape_domains_flow
        print("[OK] overnight_scraper")
    except Exception as e:
        print(f"[FAIL] overnight_scraper: {e}")
        return False
    
    return True

def test_checkpoint():
    """Test checkpoint manager."""
    print("\nTesting checkpoint manager...")
    try:
        from orchestration.checkpoint_manager import CheckpointManager
        cm = CheckpointManager()
        checkpoint = cm.create_new_checkpoint()
        print(f"[OK] Created checkpoint: {checkpoint['run_id']}")
        loaded = cm.load_checkpoint()
        if loaded and loaded['run_id'] == checkpoint['run_id']:
            print("[OK] Checkpoint save/load works")
        else:
            print("[WARN] Checkpoint not loaded correctly")
        return True
    except Exception as e:
        print(f"[FAIL] Checkpoint test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_domain_list():
    """Test domain list loading."""
    print("\nTesting domain list...")
    try:
        from orchestration.domain_boundary import load_domain_list
        domains = load_domain_list('config/bpo_sites.txt')
        print(f"[OK] Loaded {len(domains)} domains")
        if len(domains) > 0:
            print(f"  Example: {domains[0]}")
        return True
    except Exception as e:
        print(f"[FAIL] Domain list test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    print("="*80)
    print("Overnight Scraper Setup Test")
    print("="*80)
    
    all_passed = True
    all_passed = test_imports() and all_passed
    all_passed = test_checkpoint() and all_passed
    all_passed = test_domain_list() and all_passed
    
    print("\n" + "="*80)
    if all_passed:
        print("[SUCCESS] All tests passed! Setup is ready.")
    else:
        print("[FAILED] Some tests failed. Please fix issues before running.")
    print("="*80)

