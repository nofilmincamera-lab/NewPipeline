# BPO Intelligence Scraping Pipeline - Complete Documentation

## Table of Contents
1. [Pipeline Overview](#pipeline-overview)
2. [Step-by-Step Pipeline Flow](#step-by-step-pipeline-flow)
3. [Security Detection System](#security-detection-system)
4. [Anti-Bot Protection Handling](#anti-bot-protection-handling)
5. [Scraping Strategies](#scraping-strategies)
6. [Data Processing](#data-processing)
7. [Storage and Persistence](#storage-and-persistence)

---

## Pipeline Overview

The BPO Intelligence scraping pipeline is a multi-tier, intelligent web scraping system designed to handle various levels of website protection and anti-bot measures. The system automatically detects security measures and adapts its scraping strategy accordingly.

### Architecture Components

```
┌─────────────────────────────────────────────────────────────┐
│                    Pipeline Architecture                     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐      ┌──────────────┐                    │
│  │   Prefect    │──────│ Orchestration│                    │
│  │ Orchestrator │      │   Manager    │                    │
│  └──────────────┘      └──────────────┘                    │
│         │                      │                            │
│         ▼                      ▼                            │
│  ┌──────────────────────────────────────┐                  │
│  │      Security Assessment Layer       │                  │
│  │  - Security Detector                 │                  │
│  │  - Anti-Bot Detection                │                  │
│  │  - Strategy Selection                │                  │
│  └──────────────────────────────────────┘                  │
│         │                                                  │
│         ▼                                                  │
│  ┌──────────────────────────────────────┐                  │
│  │      Scraping Execution Layer        │                  │
│  │  - Tier 1: Direct HTTP (curl-cffi)   │                  │
│  │  - Tier 2: Proxy + HTTP              │                  │
│  │  - Tier 3: Browser Automation        │                  │
│  └──────────────────────────────────────┘                  │
│         │                                                  │
│         ▼                                                  │
│  ┌──────────────────────────────────────┐                  │
│  │      Content Processing Layer        │                  │
│  │  - HTML Parsing                      │                  │
│  │  - Boilerplate Removal               │                  │
│  │  - Markdown Conversion               │                  │
│  │  - File Extraction                   │                  │
│  └──────────────────────────────────────┘                  │
│         │                                                  │
│         ▼                                                  │
│  ┌──────────────────────────────────────┐                  │
│  │      Storage Layer                   │                  │
│  │  - PostgreSQL (Structured Data)      │                  │
│  │  - File System (Downloaded Files)    │                  │
│  │  - Redis (Caching)                   │                  │
│  └──────────────────────────────────────┘                  │
└─────────────────────────────────────────────────────────────┘
```

---

## Step-by-Step Pipeline Flow

### Phase 1: Initialization and Configuration

#### Step 1.1: System Startup
- **Docker Services**: All services start in order (PostgreSQL → Redis → Prefect → Scraper Core → Playwright Pool)
- **Health Checks**: Each service verifies connectivity to dependencies
- **Configuration Load**: System loads `scraper_config.yaml` and `bpo_sites.txt`
- **Database Initialization**: Tables are created/verified (scraped_sites, domain_proxy_requirements, proxy_usage_log)

#### Step 1.2: Domain List Loading
- Reads target domains from `config/bpo_sites.txt` (one URL per line)
- Validates URLs and normalizes them
- Creates domain queue for processing

#### Step 1.3: Checkpoint Recovery (if applicable)
- Checks for existing checkpoint file
- Resumes from last successful domain if interrupted
- Loads previously processed domain list

---

### Phase 2: Security Assessment

#### Step 2.1: Initial Domain Request
- **Method**: Direct HTTP request using `curl-cffi` with Chrome impersonation
- **Purpose**: Gather initial response data for security analysis
- **Timeout**: 30 seconds
- **Headers**: Standard browser headers (User-Agent, Accept, etc.)

#### Step 2.2: Security Detection Analysis
The `SecurityDetector` analyzes the response across multiple dimensions:

**2.2.1 HTTP Status Code Analysis**
- **403 Forbidden**: Indicates IP blocking or access denial
- **429 Too Many Requests**: Rate limiting detected
- **200 OK**: Normal response (further analysis needed)
- **Other codes**: Evaluated for security implications

**2.2.2 Header Analysis**
- **Cloudflare Detection**:
  - Checks for `cf-ray`, `cf-request-id`, `cf-cache-status`, `cf-visitor` headers
  - Identifies `server: cloudflare` header
  - Looks for Cloudflare-specific cookies (`__cf_bm`, `__cfduid`, `cf_clearance`)
  
- **Akamai Detection**:
  - Scans for `akamai-*` and `x-akamai-*` headers
  - Identifies Akamai Bot Manager presence
  
- **General Security Headers**:
  - `x-frame-options`
  - `x-content-type-options`
  - `strict-transport-security`
  - `content-security-policy`

**2.2.3 Content Pattern Analysis**
- **Cloudflare Challenge Pages**:
  - Searches for text: "checking your browser", "just a moment", "please wait"
  - Detects DDoS protection messages
  - Identifies JavaScript challenge requirements
  
- **CAPTCHA Detection**:
  - reCAPTCHA patterns
  - hCAPTCHA patterns
  - Cloudflare Turnstile
  - Generic CAPTCHA indicators
  
- **JavaScript Challenge Detection**:
  - "javascript required" messages
  - "enable javascript" prompts
  - `<noscript>` tags with challenge content
  - Cloudflare challenge scripts (`window._cf_chl_opt`)

**2.2.4 Response Pattern Analysis**
- **Empty/Minimal Content**: Content < 1000 chars with 200 status (possible challenge)
- **Response Time**: Unusually long response times may indicate challenges
- **Redirect Loops**: Detected and flagged

#### Step 2.3: Security Level Classification

The system classifies each domain into one of four security levels:

**LOW Security**
- No protection detected
- Direct HTTP access works
- Standard headers only
- Full content returned immediately

**MEDIUM Security**
- Basic protection (rate limiting, IP blocks)
- Proxy may help bypass restrictions
- Some headers indicate protection but content accessible
- May require retry logic

**HIGH Security**
- Strong protection (Cloudflare, Akamai)
- Requires proxy + browser automation
- JavaScript challenges present
- Browser fingerprinting likely

**CRITICAL Security**
- Very strong protection
- CAPTCHA challenges
- May require residential proxy + browser
- Advanced bot detection (behavioral analysis)

#### Step 2.4: Strategy Selection

Based on security assessment, the system selects an appropriate scraping strategy:

```python
Strategy Selection Logic:
├── LOW Security
│   └── Strategy: Direct HTTP (Tier 1)
│       ├── Method: curl-cffi with Chrome impersonation
│       ├── Proxy: Not required
│       └── Browser: Not required
│
├── MEDIUM Security
│   └── Strategy: Proxy + HTTP (Tier 2)
│       ├── Method: curl-cffi with proxy
│       ├── Proxy: Datacenter proxy (Apify)
│       └── Browser: Not required
│
├── HIGH Security
│   └── Strategy: Proxy + Browser (Tier 3)
│       ├── Method: Playwright browser automation
│       ├── Proxy: Datacenter or Residential proxy
│       └── Browser: Headless Chrome/Firefox
│
└── CRITICAL Security
    └── Strategy: Residential Proxy + Browser (Tier 3+)
        ├── Method: Playwright with stealth plugins
        ├── Proxy: Residential proxy (Apify)
        └── Browser: Full browser with human-like behavior
```

#### Step 2.5: Domain Proxy Requirements Storage

The security assessment results are stored in `domain_proxy_requirements` table:
- Domain name
- Requires proxy (boolean)
- Preferred provider
- Last direct attempt timestamp
- Success/failure counts
- Security type and level
- Strategy recommendations

---

### Phase 3: Scraping Execution

#### Step 3.1: Strategy Execution

**Tier 1: Direct HTTP Scraping**
- **Tool**: `curl-cffi` library with Chrome 110 impersonation
- **Features**:
  - TLS fingerprinting matching Chrome
  - Standard browser headers
  - Cookie handling
  - Redirect following
- **Use Case**: Sites with no or minimal protection
- **Anti-Bot Avoidance**:
  - TLS fingerprint matching (avoids basic TLS fingerprinting)
  - Browser-like headers (avoids header-based detection)
  - Realistic request timing (avoids timing-based detection)

**Tier 2: Proxy + HTTP Scraping**
- **Tool**: `curl-cffi` with Apify proxy
- **Proxy Type**: Datacenter proxy
- **Features**:
  - IP rotation
  - Geographic selection (US by default)
  - Same TLS fingerprinting as Tier 1
- **Use Case**: Sites with IP blocking or rate limiting
- **Anti-Bot Avoidance**:
  - IP rotation (avoids IP-based blocking)
  - Geographic diversity (avoids geo-based restrictions)
  - All Tier 1 protections

**Tier 3: Browser Automation**
- **Tool**: Playwright with stealth plugins
- **Browser**: Headless Chrome/Firefox
- **Features**:
  - Full JavaScript execution
  - Cookie and session management
  - Network interception
  - Screenshot capability
- **Use Case**: Sites with JavaScript challenges or advanced bot detection
- **Anti-Bot Avoidance**:
  - Full browser environment (avoids headless detection)
  - JavaScript execution (solves JS challenges)
  - Real browser fingerprint (avoids canvas/WebGL fingerprinting)
  - Stealth plugins (avoids automation detection)
  - Human-like behavior (mouse movements, delays)

#### Step 3.2: Domain Crawling

For each domain, the system performs breadth-first crawling:

1. **Start URL**: Initial domain URL from site list
2. **Link Extraction**: Parses HTML to find all links
3. **Domain Boundary Enforcement**: Only follows links within the same domain
4. **Depth Control**: Limits crawl depth (default: 3-5 levels)
5. **Page Limit**: Maximum pages per domain (default: 2000)
6. **Rate Limiting**: Respects configured rate limits (default: 5 req/sec)

#### Step 3.3: Page Processing

For each page discovered:

1. **Fetch**: Retrieves HTML content using selected strategy
2. **Content Validation**: Verifies content is HTML (not binary)
3. **Title Extraction**: Extracts page title from `<title>` tag
4. **Content Hash**: Calculates SHA-256 hash for deduplication
5. **Link Discovery**: Extracts links for further crawling
6. **File Detection**: Identifies downloadable files (PDF, DOC, DOCX)

---

### Phase 4: Content Processing

#### Step 4.1: HTML Parsing
- **Parser**: BeautifulSoup4 with lxml backend
- **Extraction**: Full HTML content preserved
- **Metadata**: Extracts title, meta tags, structured data

#### Step 4.2: Text Extraction
- **Method**: Extracts all text content from HTML
- **No Filtering**: Full text extracted (boilerplate filtering happens post-scrape)
- **Preservation**: Maintains original HTML for later processing

#### Step 4.3: Markdown Conversion (Post-Scrape)
- **Boilerplate Removal**: Removes headers, footers, navigation, ads
- **Tool**: `html2text` library
- **Process**:
  1. Remove boilerplate elements using `BoilerplateDetector`
  2. Convert cleaned HTML to Markdown
  3. Strip and clean markdown content
- **Storage**: Saved in `markdown_content` column

#### Step 4.4: File Download (if enabled)
- **File Types**: PDF, DOC, DOCX
- **Process**:
  1. Detects file links on pages
  2. Downloads files to `/app/data/files/`
  3. Calculates file hash for deduplication
  4. Stores metadata in `downloaded_files` table
- **Deduplication**: Prevents re-downloading same files
- **Size Limits**: Maximum 50MB per file

---

### Phase 5: Data Storage

#### Step 5.1: Database Storage

**scraped_sites Table**
- URL (unique)
- Domain
- Title
- Content hash (for deduplication)
- HTML length
- Markdown content
- Main content length
- Scraped timestamp
- Status code
- Response time
- Success/failure status
- Error messages
- Metadata (JSONB): Additional structured data

**domain_proxy_requirements Table**
- Domain (unique)
- Requires proxy (boolean)
- Preferred provider
- Security type
- Security level
- Last attempt timestamps
- Success/failure statistics

**downloaded_files Table**
- File URL
- Source page URL
- File type
- File size
- File hash
- Storage path
- Download status
- OCR status (if applicable)

#### Step 5.2: File System Storage
- **Location**: `/app/data/files/`
- **Structure**: Organized by file type (pdf/, doc/, docx/)
- **Naming**: Hash-based filenames for deduplication

#### Step 5.3: Caching (Redis)
- **Purpose**: Cache frequently accessed data
- **TTL**: Configurable expiration
- **Use Cases**:
  - Domain proxy requirements
  - Security assessment results
  - Rate limiting state

---

### Phase 6: Quality Assurance and Monitoring

#### Step 6.1: Quality Testing
- **Sample Size**: Tests 10 random pages per domain
- **Metrics**:
  - Content length
  - Markdown quality
  - Boilerplate ratio
  - Success rate
- **Reporting**: Generates quality report

#### Step 6.2: Checkpoint Management
- **Interval**: Checkpoint every 100 records
- **Data**: Saves progress (completed domains, current domain, page count)
- **Recovery**: Can resume from last checkpoint

#### Step 6.3: Logging and Monitoring
- **Logs**: Structured logging with Loguru
- **Metrics**: Tracks pages crawled, files found, errors
- **Prefect UI**: Workflow monitoring and visualization

---

## Security Detection System

### What the Security Test Tests For

The security detection system (`SecurityDetector`) performs comprehensive analysis to identify various types of anti-bot protection:

#### 1. Cloudflare Protection

**Detection Methods**:
- **Headers**: `cf-ray`, `cf-request-id`, `cf-cache-status`, `cf-visitor`, `server: cloudflare`
- **Cookies**: `__cf_bm`, `__cfduid`, `cf_clearance`
- **Content Patterns**: "checking your browser", "just a moment", "ddos protection"
- **JavaScript**: `window._cf_chl_opt` (challenge script)

**What It Detects**:
- Cloudflare DDoS protection
- Cloudflare Bot Management
- Cloudflare Turnstile (CAPTCHA alternative)
- JavaScript challenges
- Browser verification pages

**Confidence Levels**:
- **0.9+**: Server header confirms Cloudflare
- **0.8**: Cloudflare-specific headers present
- **0.7**: Content patterns match Cloudflare challenges
- **0.95**: Challenge page detected (requires browser)

#### 2. Akamai Bot Manager

**Detection Methods**:
- **Headers**: Any header containing "akamai" (case-insensitive)
- **Content Patterns**: "akamai", "bot manager"
- **Response Patterns**: Unusual headers, challenge pages

**What It Detects**:
- Akamai Bot Manager
- Akamai Bot Detection
- Akamai challenge pages

**Confidence Levels**:
- **0.8**: Akamai headers detected
- **0.7**: Content patterns match
- **HIGH level**: Requires browser automation

#### 3. CAPTCHA Systems

**Detection Methods**:
- **reCAPTCHA**: "recaptcha" in content, reCAPTCHA API calls
- **hCAPTCHA**: "hcaptcha" in content
- **Cloudflare Turnstile**: "turnstile" or "cf-turnstile" in content
- **Generic**: "captcha", "verify you are human", "prove you are not a robot"

**What It Detects**:
- Google reCAPTCHA v2/v3
- hCAPTCHA
- Cloudflare Turnstile
- Generic CAPTCHA implementations

**Confidence Levels**:
- **0.9**: CAPTCHA pattern detected
- **CRITICAL level**: Always requires browser + potentially manual solving

#### 4. JavaScript Challenges

**Detection Methods**:
- **Content**: "javascript.*required", "enable javascript"
- **HTML**: `<noscript>` tags with challenge content
- **Scripts**: Challenge-related JavaScript code
- **Cloudflare**: `window._cf_chl_opt` variable

**What It Detects**:
- JavaScript-based challenges
- Browser requirement pages
- Client-side verification
- Dynamic challenge generation

**Confidence Levels**:
- **0.8**: JavaScript challenge pattern detected
- **0.9**: Cloudflare Turnstile detected
- **HIGH level**: Requires browser automation

#### 5. Rate Limiting

**Detection Methods**:
- **Status Code**: HTTP 429 (Too Many Requests)
- **Headers**: `Retry-After`, rate limit headers
- **Response Time**: Unusually slow responses

**What It Detects**:
- Request rate limiting
- IP-based throttling
- Per-domain rate limits
- Per-session rate limits

**Confidence Levels**:
- **0.8**: 429 status code (high confidence)
- **MEDIUM level**: Proxy may help

#### 6. IP Blocking

**Detection Methods**:
- **Status Code**: HTTP 403 (Forbidden)
- **Content**: Block messages, access denied
- **Headers**: Block-related headers

**What It Detects**:
- IP address blocking
- Geographic restrictions
- Access denial
- Firewall blocks

**Confidence Levels**:
- **0.6**: 403 status (moderate confidence, could be other reasons)
- **MEDIUM level**: Proxy recommended

#### 7. Response Pattern Anomalies

**Detection Methods**:
- **Content Size**: < 1000 chars with 200 status (possible challenge)
- **Empty Responses**: No content but 200 status
- **Redirect Loops**: Multiple redirects
- **Unusual Timing**: Very slow or very fast responses

**What It Detects**:
- Hidden challenges
- Soft blocks
- Verification pages
- Bot traps

**Confidence Levels**:
- **0.4**: Minimal content anomaly (low confidence, needs investigation)
- **MEDIUM level**: May require browser

---

## Anti-Bot Protection Handling

### Protection Types by Security Level

#### LOW Security Level

**Protection Types**:
- None or minimal protection
- Basic robots.txt compliance
- Standard HTTP security headers

**Anti-Bot Measures Avoided**:
- **Basic Header Checks**: Uses realistic browser headers
- **TLS Fingerprinting**: curl-cffi matches Chrome TLS fingerprint
- **Request Timing**: Respects rate limits to appear human-like

**Strategy**: Direct HTTP with curl-cffi (Chrome impersonation)

---

#### MEDIUM Security Level

**Protection Types**:
- IP-based rate limiting
- Geographic restrictions
- Basic IP blocking
- Simple bot detection

**Anti-Bot Measures Avoided**:
- **IP Blocking**: Uses proxy rotation to change IP addresses
- **Rate Limiting**: Distributes requests across multiple IPs
- **Geographic Restrictions**: Can select proxy location
- **IP Reputation**: Uses fresh IPs from proxy pool
- **Request Patterns**: Maintains realistic timing even with proxy

**Strategy**: Proxy + HTTP (Apify datacenter proxy)

**Proxy Features**:
- Automatic IP rotation
- Geographic selection (US, EU, etc.)
- Session persistence when needed
- Cost tracking

---

#### HIGH Security Level

**Protection Types**:
- Cloudflare Bot Management
- Akamai Bot Manager
- JavaScript challenges
- Browser fingerprinting
- Behavioral analysis

**Anti-Bot Measures Avoided**:
- **JavaScript Challenges**: Full browser executes JavaScript
- **Browser Fingerprinting**:
  - Canvas fingerprinting (real browser canvas)
  - WebGL fingerprinting (real WebGL context)
  - Audio fingerprinting (real audio context)
  - Font fingerprinting (real font rendering)
- **Headless Detection**: Playwright with stealth plugins avoids headless detection
- **Automation Detection**:
  - `navigator.webdriver` property hidden
  - Chrome DevTools Protocol masked
  - Automation flags removed
- **TLS Fingerprinting**: Real browser TLS stack
- **HTTP/2 Fingerprinting**: Real browser HTTP/2 implementation
- **Behavioral Patterns**: Can simulate mouse movements, scrolling

**Strategy**: Proxy + Browser Automation (Playwright)

**Browser Features**:
- Headless Chrome/Firefox
- Stealth plugins (playwright-stealth)
- Full JavaScript execution
- Cookie and session management
- Network interception
- Screenshot capability

---

#### CRITICAL Security Level

**Protection Types**:
- CAPTCHA challenges (reCAPTCHA, hCAPTCHA, Turnstile)
- Advanced behavioral analysis
- Device fingerprinting
- Residential IP requirements
- Multi-factor verification

**Anti-Bot Measures Avoided**:
- **CAPTCHA Challenges**: 
  - Browser automation can handle some challenges
  - May require manual solving or CAPTCHA solving service
  - Turnstile can sometimes be auto-solved
- **Residential IP Requirements**: Uses residential proxies (Apify)
- **Device Fingerprinting**: Real browser provides device characteristics
- **Behavioral Analysis**: Can simulate human-like behavior
- **All HIGH level protections**

**Strategy**: Residential Proxy + Browser Automation

**Additional Features**:
- Residential proxy (appears as home internet connection)
- Enhanced stealth mode
- Human-like delays and interactions
- Mouse movement simulation
- Scroll behavior simulation

---

### Specific Anti-Bot Protection Details

#### 1. TLS Fingerprinting

**What It Is**: Analysis of TLS handshake characteristics to identify clients

**How We Avoid It**:
- **Tier 1/2**: curl-cffi uses Chrome 110 TLS fingerprint
- **Tier 3**: Real browser uses authentic TLS stack

**Detection**: Not directly detectable, but inferred from successful connections

---

#### 2. HTTP/2 Fingerprinting

**What It Is**: Analysis of HTTP/2 connection settings and behavior

**How We Avoid It**:
- **Tier 1/2**: curl-cffi mimics Chrome HTTP/2 settings
- **Tier 3**: Real browser uses authentic HTTP/2 implementation

**Detection**: Not directly detectable, but inferred from connection patterns

---

#### 3. Browser Fingerprinting

**What It Is**: Collection of browser characteristics (canvas, WebGL, fonts, etc.)

**How We Avoid It**:
- **Tier 3 Only**: Real browser provides authentic fingerprints
- Canvas rendering matches real browser
- WebGL context is genuine
- Font list matches real browser

**Detection**: Only detectable with browser automation (Tier 3)

---

#### 4. Headless Browser Detection

**What It Is**: Detection of automated/headless browsers

**How We Avoid It**:
- **Stealth Plugins**: playwright-stealth hides automation indicators
- **Property Masking**: `navigator.webdriver` hidden
- **CDP Masking**: Chrome DevTools Protocol indicators removed
- **Window Properties**: Automation flags removed

**Detection**: Detected through JavaScript checks (requires Tier 3)

---

#### 5. Behavioral Analysis

**What It Is**: Analysis of user behavior patterns (mouse, keyboard, timing)

**How We Avoid It**:
- **Rate Limiting**: Realistic request timing
- **Delays**: Random delays between actions
- **Mouse Simulation**: Can simulate mouse movements (Tier 3)
- **Scroll Simulation**: Can simulate scrolling behavior (Tier 3)

**Detection**: Partially detectable through timing analysis

---

#### 6. IP Reputation

**What It Is**: Blacklisting of known proxy/datacenter IPs

**How We Avoid It**:
- **Residential Proxies**: Use home IP addresses (Tier 3+)
- **IP Rotation**: Frequent IP changes
- **IP Diversity**: Multiple IP sources

**Detection**: Detected through IP reputation databases

---

#### 7. CAPTCHA Systems

**What It Is**: Challenge-response tests to verify human users

**How We Avoid It**:
- **Browser Automation**: Can handle some Turnstile challenges
- **Manual Solving**: May require human intervention
- **Solving Services**: Can integrate CAPTCHA solving APIs

**Detection**: Always visible in content (requires Tier 3+)

---

## Scraping Strategies

### Strategy Selection Matrix

| Security Level | Protection Type | Strategy | Proxy | Browser | Success Rate |
|---------------|----------------|----------|-------|---------|--------------|
| LOW | None/Minimal | Direct HTTP | No | No | 95%+ |
| MEDIUM | Rate Limit/IP Block | Proxy + HTTP | Datacenter | No | 80-90% |
| HIGH | Cloudflare/Akamai | Proxy + Browser | Datacenter | Yes | 70-85% |
| CRITICAL | CAPTCHA/Advanced | Residential + Browser | Residential | Yes | 50-70% |

### Strategy Execution Details

#### Strategy 1: Direct HTTP (Tier 1)

**When Used**: LOW security level

**Implementation**:
```python
curl-cffi with:
- Chrome 110 impersonation
- Realistic browser headers
- Cookie handling
- Redirect following
- TLS fingerprint matching
```

**Anti-Bot Avoidance**:
- ✅ TLS fingerprint matching
- ✅ Browser header matching
- ✅ Realistic request timing
- ❌ Cannot handle JavaScript challenges
- ❌ Cannot bypass advanced fingerprinting

**Cost**: $0 (no proxy)

**Speed**: Fastest (no proxy overhead)

---

#### Strategy 2: Proxy + HTTP (Tier 2)

**When Used**: MEDIUM security level

**Implementation**:
```python
curl-cffi with:
- Apify datacenter proxy
- IP rotation
- Geographic selection
- All Tier 1 features
```

**Anti-Bot Avoidance**:
- ✅ All Tier 1 protections
- ✅ IP rotation
- ✅ Geographic diversity
- ✅ IP reputation management
- ❌ Cannot handle JavaScript challenges
- ❌ Cannot bypass browser fingerprinting

**Cost**: ~$0.50/GB (Apify datacenter)

**Speed**: Fast (minimal proxy overhead)

---

#### Strategy 3: Proxy + Browser (Tier 3)

**When Used**: HIGH security level

**Implementation**:
```python
Playwright with:
- Headless Chrome/Firefox
- Stealth plugins
- Apify proxy (datacenter or residential)
- Full JavaScript execution
- Cookie/session management
```

**Anti-Bot Avoidance**:
- ✅ All Tier 2 protections
- ✅ JavaScript execution
- ✅ Browser fingerprinting
- ✅ Headless detection avoidance
- ✅ Automation detection avoidance
- ❌ May struggle with CAPTCHA
- ❌ Slower than HTTP-only

**Cost**: ~$0.50-2.00/GB (depending on proxy type)

**Speed**: Moderate (browser overhead)

---

#### Strategy 4: Residential + Browser (Tier 3+)

**When Used**: CRITICAL security level

**Implementation**:
```python
Playwright with:
- All Tier 3 features
- Residential proxy (Apify)
- Enhanced stealth mode
- Human-like behavior simulation
```

**Anti-Bot Avoidance**:
- ✅ All Tier 3 protections
- ✅ Residential IP addresses
- ✅ Human-like behavior
- ✅ Device fingerprinting
- ⚠️ CAPTCHA may require manual solving

**Cost**: ~$2.00-5.00/GB (residential proxy)

**Speed**: Slowest (residential proxy + browser)

---

## Data Processing

### Content Extraction Pipeline

1. **HTML Fetching**: Raw HTML retrieved
2. **Full Text Extraction**: All text extracted (no filtering)
3. **Storage**: HTML and text stored in database
4. **Post-Process**: Boilerplate removal for markdown conversion
5. **Markdown Generation**: Clean markdown created from filtered HTML

### Boilerplate Removal

**Removed Elements**:
- `<header>` tags
- `<footer>` tags
- `<nav>` tags
- `<aside>` tags
- Elements with boilerplate classes/IDs:
  - Header patterns: `header`, `topbar`, `navbar`, `menu`, `breadcrumb`
  - Footer patterns: `footer`, `bottom`, `copyright`, `legal`
  - Navigation patterns: `nav`, `navigation`, `sidebar`, `widget`
  - Advertisement patterns: `ad`, `ads`, `sponsor`, `banner`
  - Social patterns: `social`, `share`, `facebook`, `twitter`

**Process**:
1. Parse HTML with BeautifulSoup
2. Identify boilerplate elements using patterns
3. Remove identified elements
4. Convert cleaned HTML to Markdown
5. Store markdown separately from full HTML

---

## Storage and Persistence

### Database Schema

#### scraped_sites Table
- Primary storage for all scraped pages
- Includes full HTML, markdown, metadata
- Supports deduplication via content hash
- Tracks success/failure status

#### domain_proxy_requirements Table
- Stores security assessment results
- Tracks proxy requirements per domain
- Maintains success/failure statistics
- Enables strategy caching

#### downloaded_files Table
- Tracks downloaded files (PDF, DOC, DOCX)
- Links files to source pages
- Supports deduplication
- Tracks download status

### File System Storage

- **Location**: `/app/data/files/`
- **Organization**: By file type (pdf/, doc/, docx/)
- **Naming**: Hash-based for deduplication
- **Size Limits**: 50MB per file

### Caching (Redis)

- **Domain Requirements**: Cache security assessments
- **Rate Limiting**: Track request timing
- **Session Data**: Temporary session storage
- **TTL**: Configurable expiration

---

## Monitoring and Quality Assurance

### Quality Metrics

- **Content Length**: Measures extracted content size
- **Boilerplate Ratio**: Percentage of boilerplate vs. content
- **Success Rate**: Percentage of successful scrapes
- **Response Time**: Average response times
- **Error Rate**: Percentage of failed requests

### Checkpoint System

- **Frequency**: Every 100 records
- **Data**: Domain progress, page counts, errors
- **Recovery**: Automatic resume from checkpoint
- **Location**: `checkpoints/scrape_checkpoint.json`

### Logging

- **Structured Logs**: JSON-formatted logs
- **Levels**: DEBUG, INFO, WARNING, ERROR
- **Rotation**: Automatic log rotation
- **Location**: `/app/logs/`

---

## Configuration

### Key Configuration Options

**scraper_config.yaml**:
- `proxy_strategy`: never/always/intelligent
- `rate_limit`: Requests per second
- `max_retries`: Retry attempts
- `timeout`: Request timeout
- `max_content_size`: Maximum content size
- `file_download.enabled`: Enable file downloads
- `browser.enabled`: Enable browser automation
- `browser.headless`: Use headless browser

### Environment Variables

- `POSTGRES_HOST`: Database host
- `POSTGRES_DB`: Database name
- `POSTGRES_USER`: Database user
- `POSTGRES_PASSWORD_FILE`: Password file path
- `REDIS_HOST`: Redis host
- `REDIS_PORT`: Redis port
- `PREFECT_API_URL`: Prefect API URL
- `APIFY_PROXY_PASSWORD_FILE`: Apify password file

---

## Troubleshooting

### Common Issues

1. **403 Forbidden**: IP blocked → Use proxy
2. **429 Too Many Requests**: Rate limited → Reduce rate or use proxy
3. **Empty Content**: JavaScript challenge → Use browser
4. **CAPTCHA**: Requires manual solving or service
5. **Slow Performance**: Consider increasing parallel workers

### Debugging

- Check security assessment results
- Review proxy requirements table
- Examine response headers
- Analyze content patterns
- Review logs for errors

---

## Performance Optimization

### Parallel Processing

- **Workers**: Configurable parallel workers (default: 20)
- **Domain Parallelism**: Multiple domains processed simultaneously
- **Page Sequential**: Pages within domain processed sequentially

### Caching

- **Redis**: Cache security assessments
- **Database**: Cache proxy requirements
- **File System**: Cache downloaded files

### Resource Management

- **Memory**: Limits per container
- **CPU**: Limits per container
- **Network**: Rate limiting
- **Disk**: File size limits

---

## Future Enhancements

- CAPTCHA solving service integration
- Advanced behavioral simulation
- Machine learning for strategy selection
- Enhanced fingerprint randomization
- Distributed scraping across multiple servers

---

## License

Proprietary - BPO Intelligence Project

