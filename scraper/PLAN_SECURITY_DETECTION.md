# Security Detection & Proxy Strategy - Implementation Plan

## Overview
Implement intelligent security detection to determine the best scraping approach for each domain.

## Phase 1: Security Detection Module

### Features to Detect:
1. **Cloudflare Protection**
   - Check for `cf-ray` header
   - Detect Cloudflare challenge pages (JavaScript challenges)
   - Check for `__cf_bm` cookie
   - Detect Cloudflare Turnstile

2. **Akamai Bot Manager**
   - Check for `akamai-*` headers
   - Detect Akamai challenge pages

3. **Other Bot Protection**
   - Check for `x-bot-protection` headers
   - Detect CAPTCHA pages
   - Check for rate limiting (429 status)
   - Detect IP blocking (403 status patterns)

4. **Security Headers Analysis**
   - `x-frame-options`
   - `x-content-type-options`
   - `strict-transport-security`
   - `content-security-policy`

5. **Response Pattern Analysis**
   - Empty/minimal content with 200 status
   - JavaScript-heavy pages requiring browser
   - Redirect loops
   - Unusual response times

## Phase 2: Proxy Strategy Implementation

### Strategy Types:
1. **never** - Direct connection only
2. **always** - Always use proxy
3. **intelligent** - Auto-detect and adapt

### Intelligent Strategy Logic:
```
1. Try direct connection first
2. Analyze response:
   - If 200 OK with content → Direct works
   - If 403/429 → Try proxy
   - If Cloudflare challenge → Use proxy + Playwright
   - If empty/minimal content → Use proxy + Playwright
3. Store result in domain_proxy_requirements table
4. Use cached decision for future requests
```

## Phase 3: Integration Points

### Files to Create/Modify:
1. `src/detectors/security_detector.py` - Main detection logic
2. `src/detectors/__init__.py`
3. `src/proxy/proxy_manager.py` - Proxy selection and management
4. `src/proxy/__init__.py`
5. Update `src/scrapers/base.py` - Integrate detection
6. Update `src/scrapers/domain_crawler.py` - Use proxy strategy

## Phase 4: Testing & Validation

### Test Cases:
1. Cloudflare-protected sites
2. Sites with no protection
3. Rate-limited sites
4. Sites requiring JavaScript
5. Mixed scenarios

## Implementation Priority:
1. ✅ Database schema (already exists)
2. ⏳ Security detection module
3. ⏳ Proxy manager
4. ⏳ Integration with scrapers
5. ⏳ Testing and validation

