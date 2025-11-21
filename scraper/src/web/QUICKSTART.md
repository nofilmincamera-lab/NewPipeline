# Quick Start Guide

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

## Running the Viewer

### Option 1: Using the run script (Recommended)
```bash
cd scraper/src/web
python run.py
```

### Option 2: Direct Python execution
```bash
cd scraper
python -m src.web.app
```

### Option 3: Using uvicorn directly
```bash
uvicorn scraper.src.web.app:app --host 0.0.0.0 --port 8000 --reload
```

## Access the Viewer

Open your browser to: **http://localhost:8000**

## Features

- **Home Page (`/`)**: Browse all organizations with search functionality
- **Organization Detail (`/organization/{id}`)**: View complete organization profile
- **Corporate Entities (`/entities`)**: Browse all corporate entities
- **Entity Detail (`/entity/{id}`)**: View entity hierarchy and relationships
- **Statistics (`/stats`)**: View database statistics and breakdowns
- **Health Check (`/health`)**: Check if the service is running and database is connected
- **API (`/api/organizations`)**: JSON API endpoint

## Troubleshooting

### Database Connection Errors

1. **Check PostgreSQL is running:**
   ```bash
   # On Windows
   Get-Service postgresql*
   
   # On Linux/Mac
   sudo systemctl status postgresql
   ```

2. **Verify database exists:**
   ```sql
   \l  -- List databases
   ```

3. **Check password file:**
   - Location: `ops/secrets/postgres_password.txt`
   - Or the app will use default password "postgres"

4. **Test connection manually:**
   ```python
   import asyncpg
   conn = await asyncpg.connect(
       host="localhost",
       database="bpo_intelligence",
       user="bpo_user",
       password="your_password"
   )
   ```

### Port Already in Use

If port 8000 is already in use, change it in `run.py`:
```python
uvicorn.run(app, host="0.0.0.0", port=8080)  # Use different port
```

### Import Errors

Make sure you're running from the correct directory or have the project root in your Python path.

## Logs

Logs are written to `web_viewer.log` in the web directory.

