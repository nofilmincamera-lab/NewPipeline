#!/usr/bin/env python3
"""
Test script for security detection
Tests various sites to detect their security measures
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from curl_cffi import requests
from src.detectors.security_detector import SecurityDetector, SecurityType, SecurityLevel

async def test_security_detection():
    """Test security detection on various URLs"""
    
    detector = SecurityDetector()
    session = requests.Session()
    
    # Test URLs - mix of protected and unprotected sites
    test_urls = [
        'https://foundever.com',
        'https://cloudflare.com',  # Likely has Cloudflare
        'https://example.com',     # Simple site
        'https://httpbin.org/status/403',  # Test 403
        'https://httpbin.org/status/429',  # Test 429
    ]
    
    print("="*80)
    print("SECURITY DETECTION TEST")
    print("="*80)
    print()
    
    for url in test_urls:
        try:
            print(f"Testing: {url}")
            print("-" * 80)
            
            # Fetch page
            response = session.get(url, timeout=10, allow_redirects=True)
            
            # Detect security
            result = detector.detect(
                url=url,
                status_code=response.status_code,
                headers=dict(response.headers),
                content=response.text[:5000],  # First 5KB for analysis
                response_time=None
            )
            
            # Print results
            print(f"Status Code: {response.status_code}")
            print(f"Security Type: {result['security_type'].value}")
            print(f"Security Level: {result['security_level'].value}")
            print(f"Requires Proxy: {result['requires_proxy']}")
            print(f"Requires Browser: {result['requires_browser']}")
            print(f"Confidence: {result['confidence']:.2%}")
            
            if result['indicators']:
                print(f"Indicators:")
                for indicator in result['indicators']:
                    print(f"  - {indicator}")
            
            print()
            
        except Exception as e:
            print(f"Error testing {url}: {e}")
            print()
    
    print("="*80)

if __name__ == '__main__':
    asyncio.run(test_security_detection())

