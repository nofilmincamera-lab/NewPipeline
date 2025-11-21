# Running Overnight Scraper with Docker Prefect Server

## Overview

The Prefect server is running in Docker (`bpo-prefect-server`), but the Python code can run locally and connect to it via API.

## Current Status

### Prefect Server in Docker
- **Container**: `bpo-prefect-server`
- **Image**: `prefecthq/prefect:3.1.9-python3.11`
- **Port**: `4200:4200`
- **API URL**: `http://localhost:4200/api`
- **Status**: Currently restarting (database password issue)

### Local Python
- **Version**: Python 3.13
- **Prefect**: Installed but has import issues
- **Issue**: `ModuleNotFoundError: No module named 'prefect.utilities'`

## Solutions

### Option 1: Fix Prefect Server (Recommended)

The Prefect server is restarting due to database password authentication. Fix it:

1. **Check PostgreSQL is running**:
   ```bash
   docker ps | grep postgres
   ```

2. **Check password secret file**:
   ```bash
   cat ops/secrets/postgres_password.txt
   ```

3. **Restart Prefect server**:
   ```bash
   docker-compose restart prefect-server
   ```

4. **Check logs**:
   ```bash
   docker logs bpo-prefect-server -f
   ```

### Option 2: Run Everything in Docker

Run the scraper inside Docker where Prefect is properly installed:

```bash
docker-compose up -d scraper-core
docker exec -it bpo-scraper-core python run_overnight_scraper.py
```

### Option 3: Fix Local Prefect Installation

Reinstall Prefect properly:

```bash
pip uninstall prefect
pip install prefect==3.1.9
```

Or use a virtual environment with Python 3.11 (matching Docker):

```bash
# Create venv with Python 3.11
python3.11 -m venv venv_prefect
source venv_prefect/bin/activate  # or venv_prefect\Scripts\activate on Windows
pip install prefect==3.1.9
```

### Option 4: Run Without Prefect (Standalone Mode)

The code now has fallback decorators. You can run without Prefect (but without Prefect UI monitoring):

```bash
# This will run but won't connect to Prefect server
python scraper/run_overnight_scraper.py
```

## Configuration

The code automatically sets `PREFECT_API_URL` to `http://localhost:4200/api` to connect to the Docker server.

You can override it:

```bash
export PREFECT_API_URL=http://localhost:4200/api
python scraper/run_overnight_scraper.py
```

## Verification

1. **Check Prefect server is running**:
   ```bash
   docker ps | grep prefect
   curl http://localhost:4200/health
   ```

2. **Test connection**:
   ```bash
   python scraper/check_prefect_server.py
   ```

3. **Run scraper**:
   ```bash
   python scraper/run_overnight_scraper.py
   ```

## Next Steps

1. Fix Prefect server database connection issue
2. Verify server is accessible at http://localhost:4200
3. Run scraper with proper Prefect connection

Once the Prefect server is stable, you can monitor flows at:
- **Prefect UI**: http://localhost:4200
- **API**: http://localhost:4200/api

