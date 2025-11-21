"""
Security Detection - Identify site security measures to determine scraping approach
"""

import re
from typing import Dict, Optional, Any, Set
from enum import Enum
from bs4 import BeautifulSoup


class SecurityType(Enum):
    """Types of security measures detected"""
    NONE = "none"
    CLOUDFLARE = "cloudflare"
    AKAMAI = "akamai"
    CAPTCHA = "captcha"
    RATE_LIMIT = "rate_limit"
    IP_BLOCK = "ip_block"
    JAVASCRIPT_CHALLENGE = "javascript_challenge"
    UNKNOWN = "unknown"


class SecurityLevel(Enum):
    """Security level classification"""
    LOW = "low"           # No protection, direct access works
    MEDIUM = "medium"     # Basic protection, proxy may help
    HIGH = "high"         # Strong protection, requires proxy + browser
    CRITICAL = "critical" # Very strong protection, may need residential proxy + browser


class SecurityDetector:
    """Detect security measures on websites"""
    
    # Cloudflare indicators
    CLOUDFLARE_HEADERS = {
        'cf-ray',
        'cf-request-id',
        'cf-cache-status',
        'cf-visitor',
        'server'  # Often "cloudflare"
    }
    
    CLOUDFLARE_COOKIES = {
        '__cf_bm',
        '__cfduid',
        'cf_clearance'
    }
    
    CLOUDFLARE_INDICATORS = [
        r'cloudflare',
        r'cf-ray',
        r'checking your browser',
        r'ddos protection',
        r'just a moment',
        r'please wait',
        r'__cf_bm'
    ]
    
    # Akamai indicators
    AKAMAI_HEADERS = {
        'akamai-*',
        'x-akamai-*'
    }
    
    AKAMAI_INDICATORS = [
        r'akamai',
        r'akamai-',
        r'bot manager'
    ]
    
    # CAPTCHA indicators
    CAPTCHA_INDICATORS = [
        r'recaptcha',
        r'hcaptcha',
        r'captcha',
        r'turnstile',
        r'verify you are human',
        r'prove you are not a robot'
    ]
    
    # JavaScript challenge indicators
    JS_CHALLENGE_INDICATORS = [
        r'javascript.*required',
        r'enable javascript',
        r'noscript',
        r'<script.*challenge',
        r'window\._cf_chl_opt'
    ]
    
    def __init__(self):
        """Initialize security detector"""
        pass
    
    def detect(
        self,
        url: str,
        status_code: int,
        headers: Dict[str, str],
        content: Optional[str] = None,
        response_time: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Detect security measures from response.
        
        Args:
            url: Requested URL
            status_code: HTTP status code
            headers: Response headers
            content: Response content (optional)
            response_time: Response time in seconds (optional)
            
        Returns:
            Dictionary with detection results:
            {
                'security_type': SecurityType,
                'security_level': SecurityLevel,
                'requires_proxy': bool,
                'requires_browser': bool,
                'indicators': List[str],
                'confidence': float  # 0.0 to 1.0
            }
        """
        results = {
            'security_type': SecurityType.NONE,
            'security_level': SecurityLevel.LOW,
            'requires_proxy': False,
            'requires_browser': False,
            'indicators': [],
            'confidence': 0.0
        }
        
        # Normalize headers to lowercase keys
        headers_lower = {k.lower(): v for k, v in headers.items()}
        content_lower = content.lower() if content else ""
        
        # Check status code patterns
        if status_code == 403:
            results['security_type'] = SecurityType.IP_BLOCK
            results['security_level'] = SecurityLevel.MEDIUM
            results['requires_proxy'] = True
            results['indicators'].append('403 Forbidden')
            results['confidence'] = 0.6
        
        if status_code == 429:
            results['security_type'] = SecurityType.RATE_LIMIT
            results['security_level'] = SecurityLevel.MEDIUM
            results['requires_proxy'] = True
            results['indicators'].append('429 Too Many Requests')
            results['confidence'] = 0.8
        
        # Detect Cloudflare
        cf_detected = self._detect_cloudflare(headers_lower, content_lower)
        if cf_detected['detected']:
            results['security_type'] = SecurityType.CLOUDFLARE
            results['security_level'] = cf_detected['level']
            results['requires_proxy'] = True
            results['requires_browser'] = cf_detected['requires_browser']
            results['indicators'].extend(cf_detected['indicators'])
            results['confidence'] = max(results['confidence'], cf_detected['confidence'])
        
        # Detect Akamai
        akamai_detected = self._detect_akamai(headers_lower, content_lower)
        if akamai_detected['detected']:
            if results['security_type'] == SecurityType.NONE:
                results['security_type'] = SecurityType.AKAMAI
                results['security_level'] = akamai_detected['level']
                results['requires_proxy'] = True
                results['requires_browser'] = akamai_detected['requires_browser']
                results['indicators'].extend(akamai_detected['indicators'])
                results['confidence'] = max(results['confidence'], akamai_detected['confidence'])
        
        # Detect CAPTCHA
        captcha_detected = self._detect_captcha(content_lower)
        if captcha_detected['detected']:
            results['security_type'] = SecurityType.CAPTCHA
            results['security_level'] = SecurityLevel.CRITICAL
            results['requires_proxy'] = True
            results['requires_browser'] = True
            results['indicators'].extend(captcha_detected['indicators'])
            results['confidence'] = max(results['confidence'], captcha_detected['confidence'])
        
        # Detect JavaScript challenges
        js_challenge = self._detect_js_challenge(content)
        if js_challenge['detected']:
            if results['security_type'] == SecurityType.NONE:
                results['security_type'] = SecurityType.JAVASCRIPT_CHALLENGE
                results['security_level'] = SecurityLevel.HIGH
                results['requires_browser'] = True
                results['requires_proxy'] = True
                results['indicators'].extend(js_challenge['indicators'])
                results['confidence'] = max(results['confidence'], js_challenge['confidence'])
        
        # Check for empty/minimal content (possible challenge)
        if content and len(content.strip()) < 1000 and status_code == 200:
            results['indicators'].append('Minimal content with 200 status')
            if results['security_type'] == SecurityType.NONE:
                results['security_level'] = SecurityLevel.MEDIUM
                results['confidence'] = 0.4
        
        return results
    
    def _detect_cloudflare(
        self,
        headers: Dict[str, str],
        content: str
    ) -> Dict[str, Any]:
        """Detect Cloudflare protection"""
        detected = False
        indicators = []
        confidence = 0.0
        requires_browser = False
        level = SecurityLevel.LOW
        
        # Check headers
        for header_name in headers:
            if any(cf_header in header_name for cf_header in ['cf-ray', 'cf-request', 'cf-cache', 'cf-visitor']):
                detected = True
                indicators.append(f"Cloudflare header: {header_name}")
                confidence = 0.8
        
        # Check server header
        server = headers.get('server', '').lower()
        if 'cloudflare' in server:
            detected = True
            indicators.append(f"Cloudflare server: {server}")
            confidence = 0.9
        
        # Check content for Cloudflare indicators
        for pattern in self.CLOUDFLARE_INDICATORS:
            if re.search(pattern, content, re.IGNORECASE):
                detected = True
                indicators.append(f"Cloudflare content pattern: {pattern}")
                confidence = max(confidence, 0.7)
                
                # Check for challenge pages
                if any(phrase in content.lower() for phrase in ['checking your browser', 'just a moment', 'please wait']):
                    requires_browser = True
                    level = SecurityLevel.HIGH
                    confidence = 0.95
        
        return {
            'detected': detected,
            'level': level,
            'requires_browser': requires_browser,
            'indicators': indicators,
            'confidence': confidence
        }
    
    def _detect_akamai(
        self,
        headers: Dict[str, str],
        content: str
    ) -> Dict[str, Any]:
        """Detect Akamai Bot Manager"""
        detected = False
        indicators = []
        confidence = 0.0
        requires_browser = False
        level = SecurityLevel.MEDIUM
        
        # Check headers
        for header_name in headers:
            if 'akamai' in header_name.lower():
                detected = True
                indicators.append(f"Akamai header: {header_name}")
                confidence = 0.8
        
        # Check content
        for pattern in self.AKAMAI_INDICATORS:
            if re.search(pattern, content, re.IGNORECASE):
                detected = True
                indicators.append(f"Akamai content pattern: {pattern}")
                confidence = max(confidence, 0.7)
                level = SecurityLevel.HIGH
                requires_browser = True
        
        return {
            'detected': detected,
            'level': SecurityLevel.HIGH if requires_browser else SecurityLevel.MEDIUM,
            'requires_browser': requires_browser,
            'indicators': indicators,
            'confidence': confidence
        }
    
    def _detect_captcha(self, content: str) -> Dict[str, Any]:
        """Detect CAPTCHA challenges"""
        detected = False
        indicators = []
        confidence = 0.0
        
        for pattern in self.CAPTCHA_INDICATORS:
            if re.search(pattern, content, re.IGNORECASE):
                detected = True
                indicators.append(f"CAPTCHA pattern: {pattern}")
                confidence = 0.9
        
        return {
            'detected': detected,
            'indicators': indicators,
            'confidence': confidence
        }
    
    def _detect_js_challenge(self, content: Optional[str]) -> Dict[str, Any]:
        """Detect JavaScript challenges"""
        if not content:
            return {'detected': False, 'indicators': [], 'confidence': 0.0}
        
        detected = False
        indicators = []
        confidence = 0.0
        
        content_lower = content.lower()
        
        for pattern in self.JS_CHALLENGE_INDICATORS:
            if re.search(pattern, content_lower):
                detected = True
                indicators.append(f"JS challenge pattern: {pattern}")
                confidence = 0.8
        
        # Check for Cloudflare Turnstile
        if 'turnstile' in content_lower or 'cf-turnstile' in content_lower:
            detected = True
            indicators.append("Cloudflare Turnstile detected")
            confidence = 0.9
        
        return {
            'detected': detected,
            'indicators': indicators,
            'confidence': confidence
        }
    
    def should_use_proxy(self, detection_result: Dict[str, Any]) -> bool:
        """Determine if proxy should be used based on detection"""
        return detection_result.get('requires_proxy', False)
    
    def should_use_browser(self, detection_result: Dict[str, Any]) -> bool:
        """Determine if browser automation should be used"""
        return detection_result.get('requires_browser', False)

