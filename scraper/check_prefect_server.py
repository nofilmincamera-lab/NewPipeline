#!/usr/bin/env python3
"""
Check Prefect Server Connection

Verifies that Prefect server is accessible and configured correctly.
"""

import os
import sys
import requests
from pathlib import Path

def check_prefect_server():
    """Check if Prefect server is accessible."""
    print("=" * 80)
    print("Prefect Server Connection Check")
    print("=" * 80)
    
    # Check environment variable
    api_url = os.environ.get('PREFECT_API_URL', 'http://localhost:4200/api')
    print(f"\n[1] Prefect API URL: {api_url}")
    
    # Test server health
    try:
        health_url = api_url.rstrip('/api') + '/health'
        print(f"[2] Testing server health at: {health_url}")
        
        response = requests.get(health_url, timeout=5)
        if response.status_code == 200:
            print("[OK] Server is responding")
            try:
                data = response.json()
                print(f"     Response: {data}")
            except:
                print(f"     Response text: {response.text[:100]}")
        else:
            print(f"[WARN] Server returned status {response.status_code}")
            print(f"     Response: {response.text[:200]}")
    except requests.exceptions.ConnectionError:
        print("[FAIL] Cannot connect to Prefect server")
        print("       Make sure Prefect server is running in WSL2:")
        print("       Check with: prefect server start")
        print("       Or see: scraper/install_prefect_wsl2.sh")
        return False
    except Exception as e:
        print(f"[FAIL] Error checking server: {e}")
        return False
    
    # Check Python Prefect package
    print(f"\n[3] Checking Python Prefect package...")
    try:
        import prefect
        print(f"[OK] Prefect package installed: {prefect.__version__}")
    except ImportError as e:
        print(f"[FAIL] Prefect package not installed: {e}")
        print("       Install with: pip install prefect==3.1.9")
        return False
    
    # Try to import flow decorator
    print(f"\n[4] Testing Prefect imports...")
    try:
        from prefect import flow, task
        print("[OK] Can import flow and task decorators")
    except ImportError as e:
        print(f"[WARN] Cannot import flow/task: {e}")
        print("       This might be OK if running flows via Docker")
        print("       Or try: pip install --upgrade prefect==3.1.9")
    
    print("\n" + "=" * 80)
    print("Summary:")
    print("  - Server accessible: Check [2]")
    print("  - Python package: Check [3]")
    print("  - Imports working: Check [4]")
    print("=" * 80)
    
    return True


if __name__ == '__main__':
    try:
        check_prefect_server()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

