# Overnight Scraper Setup Guide

## Quick Start

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Verify Setup**
   ```bash
   python test_overnight_setup.py
   ```

3. **Start Prefect Server** (if using Docker)
   ```bash
   docker-compose up -d prefect-server
   ```

4. **Run Overnight Scraper**
   ```bash
   python run_overnight_scraper.py
   ```

## Prerequisites

- Python 3.11+
- PostgreSQL database running
- Prefect 3.1.9 (included in requirements.txt)
- All dependencies from requirements.txt

## Configuration Files

- **Domain List**: `config/bpo_sites.txt` (73 domains)
- **Scraper Config**: `config/scraper_config.yaml`
- **Checkpoint**: `checkpoints/scrape_checkpoint.json` (auto-created)
- **Logs**: `logs/scrape_run_*.md` (auto-created)

## System Status

### ✓ Completed Components

- ✅ Checkpoint Manager - Save/load/resume functionality
- ✅ Markdown Logger - Structured logging system
- ✅ Domain Boundary Checker - URL validation
- ✅ Domain List Loader - Loads 73 domains
- ✅ Security Assessment Task - Uses SecurityDetector API
- ✅ Quality Test Task - 10-record sample with 15% text ratio threshold
- ✅ Full Domain Scrape Task - Up to 2,000 records per domain
- ✅ Prefect Flow Orchestration - Main flow with retry policies

### ⚠️ Pending Installation

- ⚠️ Prefect 3.1.9 - Install with: `pip install prefect==3.1.9`

## Features

### 1. Checkpoint Recovery
- Auto-saves after each domain
- Resumes from last successful domain
- Expires checkpoints older than 24 hours
- Tracks completed, marked-for-review, and manual-review domains

### 2. Parallel Processing
- Configurable workers (default: 10)
- Processes 8-12 domains concurrently
- Batch processing for stability

### 3. Security Assessment
- Automatic detection (Cloudflare, bot detection, etc.)
- Strategy selection based on security level
- Fingerprint logging for troubleshooting

### 4. Quality Testing
- Extracts 10 sample records before full scrape
- Calculates text-to-HTML ratio
- Threshold: 15% minimum text ratio
- Skips domains with low quality

### 5. Domain Boundaries
- Supports subdomains (blog.worldline.com)
- Supports derivative domains (worldline-solutions.com)
- Allows direct file downloads

### 6. Error Categorization
- ✅ **SUCCESS**: Security handled, quality passed, records extracted
- ⚠️ **MARKED_FOR_REVIEW**: Low quality or partial success
- 🔴 **MANUAL_REVIEW**: No strategy available or custom protection

## Usage Examples

### Basic Run (Resume from Checkpoint)
```bash
python run_overnight_scraper.py
```

### Start Fresh (Ignore Checkpoint)
```bash
python run_overnight_scraper.py --fresh
```

### Custom Worker Count
```bash
python run_overnight_scraper.py --workers 12
```

### Combined Options
```bash
python run_overnight_scraper.py --fresh --workers 8
```

## Monitoring

### Prefect UI
- URL: http://localhost:4200
- View: Flow runs, task status, logs
- Note: Requires Prefect server running

### Markdown Logs
- Location: `logs/scrape_run_YYYY-MM-DD_HH-MM-SS.md`
- Contains: Full execution log, domain results, summary

### Checkpoint File
- Location: `checkpoints/scrape_checkpoint.json`
- Format: JSON with completed domains, statistics, in-progress state

## Expected Workflow

1. **Load Domain List** (73 domains)
2. **Check Checkpoint** (resume if available)
3. **Process Domains in Batches** (10 workers)
   - Security Assessment
   - Quality Test (10 records)
   - Full Scrape (up to 2,000 records)
4. **Save Checkpoint** (after each domain)
5. **Generate Summary** (markdown log)

## Troubleshooting

### Prefect Not Installed
```bash
pip install prefect==3.1.9
```

### Checkpoint Not Loading
- Check file exists: `checkpoints/scrape_checkpoint.json`
- Verify age < 24 hours
- Use `--fresh` to start new run

### Database Connection Issues
- Verify PostgreSQL is running
- Check credentials in `config/scraper_config.yaml`
- Test connection with: `python check_and_init_db.py`

### Low Quality Scores
- Many sites are JavaScript-heavy
- Consider enabling browser rendering in config
- Check markdown logs for details

## Next Steps

1. **Install Prefect**: `pip install prefect==3.1.9`
2. **Run Test**: `python test_overnight_setup.py`
3. **Start Server**: `docker-compose up -d prefect-server` (if using Docker)
4. **Run Scraper**: `python run_overnight_scraper.py`

## File Structure

```
scraper/
├── src/orchestration/
│   ├── checkpoint_manager.py      # Checkpoint save/load
│   ├── markdown_logger.py         # Markdown logging
│   ├── domain_boundary.py         # URL boundary checking
│   └── overnight_scraper.py       # Main Prefect flow
├── run_overnight_scraper.py       # Runner script
├── test_overnight_setup.py        # Setup verification
├── checkpoints/                   # Checkpoint files (auto-created)
├── logs/                          # Markdown logs (auto-created)
└── README_OVERNIGHT_SCRAPER.md    # Detailed documentation
```

