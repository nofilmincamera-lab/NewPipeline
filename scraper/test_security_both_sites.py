#!/usr/bin/env python3
"""
Test security detection for both worldline.com and docs.connect.worldline-solutions.com
"""

import sys
from pathlib import Path
from urllib.request import urlopen, Request
import ssl

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from src.detectors.security_detector import SecurityDetector, SecurityType, SecurityLevel

def test_security(url):
    """Test security detection on a URL"""
    
    detector = SecurityDetector()
    
    print("="*80)
    print(f"TESTING SECURITY DETECTION: {url}")
    print("="*80)
    print()
    
    try:
        # Fetch page
        req = Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        # Create SSL context that doesn't verify certificates (for testing only)
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        with urlopen(req, timeout=10, context=ssl_context) as response:
            status_code = response.getcode()
            headers = {k.lower(): v for k, v in response.headers.items()}
            content = response.read().decode('utf-8', errors='ignore')[:10000]
        
        # Detect security
        result = detector.detect(
            url=url,
            status_code=status_code,
            headers=headers,
            content=content,
            response_time=None
        )
        
        # Print results
        print(f"Status Code: {status_code}")
        print(f"Security Type: {result['security_type'].value}")
        print(f"Security Level: {result['security_level'].value}")
        print(f"Requires Proxy: {result['requires_proxy']}")
        print(f"Requires Browser: {result['requires_browser']}")
        print(f"Confidence: {result['confidence']:.2%}")
        print()
        
        if result['indicators']:
            print("Indicators Found:")
            for indicator in result['indicators']:
                print(f"  - {indicator}")
            print()
        
        # Show relevant headers
        print("Relevant Security Headers:")
        relevant_headers = {
            k: v for k, v in headers.items() 
            if any(x in k.lower() for x in ['cf-', 'akamai', 'server', 'x-', 'content-security'])
        }
        if relevant_headers:
            for k, v in relevant_headers.items():
                print(f"  {k}: {v}")
        else:
            print("  (No relevant security headers found)")
        print()
        
        return result
        
    except Exception as e:
        print(f"Error testing {url}: {e}")
        import traceback
        traceback.print_exc()
        return None
    
    print("="*80)
    print()

if __name__ == '__main__':
    urls = [
        'https://worldline.com',
        'https://docs.connect.worldline-solutions.com/'
    ]
    
    results = {}
    for url in urls:
        results[url] = test_security(url)
        print()

