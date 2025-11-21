# Overnight Batch Scraper

Comprehensive Prefect-orchestrated scraping system with checkpoint recovery, parallel processing, and detailed markdown logging.

## Features

- ✅ **Checkpoint Recovery**: Resume from last successful domain
- ✅ **Parallel Processing**: 8-12 concurrent workers
- ✅ **Security Assessment**: Automatic detection and strategy selection
- ✅ **Quality Testing**: 10-record sample before full scrape
- ✅ **Markdown Logging**: Detailed logs for analysis
- ✅ **Domain Boundaries**: Supports subdomains and derivative domains
- ✅ **Error Handling**: Comprehensive retry policies and error categorization

## Setup

1. **Install Prefect Server** (if not already running):
```bash
docker-compose up -d prefect-server
```

2. **Verify Prefect UI**:
   - Open: http://localhost:4200/api
   - Prefect UI: http://localhost:4200

3. **Check Configuration**:
   - Domain list: `config/bpo_sites.txt`
   - Scraper config: `config/scraper_config.yaml`

## Usage

### Basic Run
```bash
python run_overnight_scraper.py
```

### Options
```bash
# Start fresh (ignore checkpoint)
python run_overnight_scraper.py --fresh

# Custom worker count
python run_overnight_scraper.py --workers 12

# Combine options
python run_overnight_scraper.py --fresh --workers 8
```

### Prefect Flow (Programmatic)
```python
from src.orchestration.overnight_scraper import scrape_domains_flow
import asyncio

result = asyncio.run(scrape_domains_flow(resume_from_checkpoint=True, max_workers=10))
```

## Workflow

1. **Security Assessment**: Detects protections (Cloudflare, bot detection, etc.)
2. **Quality Test**: Extracts 10 sample records to assess text-to-HTML ratio
3. **Full Scrape**: Extracts up to 2,000 records per domain
4. **Checkpointing**: Saves state after each domain
5. **Logging**: Writes detailed markdown logs

## Outputs

### Checkpoint File
- Location: `checkpoints/scrape_checkpoint.json`
- Contains: Completed domains, in-progress domain, statistics
- Auto-recovery: Resume if checkpoint < 24 hours old

### Markdown Logs
- Location: `logs/scrape_run_YYYY-MM-DD_HH-MM-SS.md`
- Contains: Full execution log, domain results, summary statistics

### Database
- Table: `scraped_sites`
- Fields: URL, domain, title, markdown_content, organization_uuid, metadata
- Linked to: `organizations` table via UUID

## Domain Categorization

### ✅ Successful
- Security: Detected and handled
- Quality: Text ratio >= 15%
- Records: Up to 2,000 extracted

### ⚠️ Marked for Review
- Quality: Low text ratio (< 15%)
- Extraction: Partial success
- Action: Manual review recommended

### 🔴 Manual Review
- Security: No strategy available
- Protection: Custom bot detection
- Action: Develop custom bypass

## Configuration

### Worker Count
- Default: 10 workers
- Recommended: 8-12 (balance throughput vs. stability)
- Adjust based on system resources

### Max Records per Domain
- Default: 2,000 records
- Configurable in `overnight_scraper.py`: `MAX_RECORDS_PER_DOMAIN`

### Checkpoint Interval
- Default: Every 100 records
- Configurable in `overnight_scraper.py`: `CHECKPOINT_INTERVAL`

## Troubleshooting

### Checkpoint Not Loading
- Check file exists: `checkpoints/scrape_checkpoint.json`
- Verify age < 24 hours
- Use `--fresh` to start new run

### Low Quality Scores
- Many sites are JavaScript-heavy
- Consider enabling browser rendering
- Check `scraper_config.yaml` browser settings

### Security Detection Failures
- Some sites require custom strategies
- Check logs for protection fingerprints
- Develop custom bypass if needed

## Monitoring

### Prefect UI
- URL: http://localhost:4200
- View: Flow runs, task status, logs

### Markdown Logs
- Location: `logs/scrape_run_*.md`
- Includes: Domain results, quality metrics, error details

### Database
```sql
-- Check scraped records
SELECT domain, COUNT(*) as records
FROM scraped_sites
WHERE success = true
GROUP BY domain
ORDER BY records DESC;

-- Check organization linking
SELECT o.canonical_name, COUNT(ss.id) as records
FROM organizations o
LEFT JOIN scraped_sites ss ON o.uuid = ss.organization_uuid
GROUP BY o.canonical_name
ORDER BY records DESC;
```

## Example Output

```
================================================================================
SCRAPING COMPLETE
================================================================================
Run ID: scrape_2025-11-21_00-00-00
Successful: 45 domains
Total Records: 67,234
Marked for Review: 12 domains
Manual Review: 8 domains
================================================================================
```

## Notes

- Notifications are disabled during overnight runs
- Rate limiting is handled per-domain
- Resource monitoring recommended for long runs
- Checkpoint recovery requires same domain list

