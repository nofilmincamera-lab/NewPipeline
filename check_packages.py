#!/usr/bin/env python3
"""
Quick package validation script for WSL2
Checks if all required packages from requirements.txt are installed
"""

import sys
import subprocess
from pathlib import Path

# Required packages from requirements.txt
REQUIRED_PACKAGES = {
    'curl_cffi': 'curl-cffi',
    'bs4': 'beautifulsoup4',
    'lxml': 'lxml',
    'playwright': 'playwright',
    'playwright_stealth': 'playwright-stealth',
    'apify': 'apify-client',
    'pandas': 'pandas',
    'pydantic': 'pydantic',
    'dateutil': 'python-dateutil',
    'html2text': 'html2text',
    'prefect': 'prefect',
    'redis': 'redis',
    'psycopg': 'psycopg',
    'asyncpg': 'asyncpg',
    'tenacity': 'tenacity',
    'ratelimit': 'ratelimit',
    'dotenv': 'python-dotenv',
    'loguru': 'loguru',
    'yaml': 'pyyaml',
    'pytest': 'pytest',
    'pytest_asyncio': 'pytest-asyncio',
}

def check_package(import_name, package_name):
    """Check if a package can be imported"""
    try:
        module = __import__(import_name)
        version = getattr(module, '__version__', 'installed')
        return True, version
    except ImportError:
        return False, None

def main():
    print("=== WSL2 Package Validation ===\n")
    
    # Check Python version
    print(f"Python version: {sys.version.split()[0]}\n")
    
    # Check pip
    try:
        result = subprocess.run(['pip3', '--version'], 
                              capture_output=True, text=True, check=True)
        print(f"pip: {result.stdout.strip()}\n")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("✗ pip3 not found!\n")
        return 1
    
    print("Checking required packages:\n")
    
    missing = []
    installed = []
    
    for import_name, package_name in REQUIRED_PACKAGES.items():
        is_installed, version = check_package(import_name, package_name)
        if is_installed:
            print(f"  ✓ {package_name:25} {version}")
            installed.append(package_name)
        else:
            print(f"  ✗ {package_name:25} NOT INSTALLED")
            missing.append(package_name)
    
    print(f"\n=== Summary ===")
    print(f"Installed: {len(installed)}/{len(REQUIRED_PACKAGES)}")
    print(f"Missing: {len(missing)}/{len(REQUIRED_PACKAGES)}")
    
    if missing:
        print(f"\n✗ Missing packages:")
        for pkg in missing:
            print(f"  - {pkg}")
        print(f"\nTo install all packages, run:")
        print(f"  cd scraper && pip3 install -r requirements.txt")
        return 1
    else:
        print(f"\n✓ All required packages are installed!")
        return 0

if __name__ == '__main__':
    sys.exit(main())

