# BPO Intelligence Web Viewer

A web interface for viewing organization profiles, facts, and relationships.

## Installation

Install dependencies:

```bash
pip install -r requirements.txt
```

## Running

### Quick Start (Windows) - RECOMMENDED
Double-click `install_and_run.bat` - this will:
1. Install all dependencies
2. Test the setup
3. Start the web viewer

Or manually:
```bash
cd scraper/src/web
pip install -r requirements.txt
python run.py
```

Then open your browser to: **http://localhost:8000**

**Note:** The server binds to `0.0.0.0:8000` which means:
- Accessible on `http://localhost:8000`
- Accessible on `http://127.0.0.1:8000`
- Accessible from other devices on your network at `http://YOUR_IP:8000`

### Quick Start (Linux/Mac)
```bash
cd scraper/src/web
chmod +x start.sh
./start.sh
```

### Manual Start
Start the web server using the run script:

```bash
cd scraper/src/web
python run.py
```

### Test Setup First
Before running, you can test if everything is set up correctly:

```bash
cd scraper/src/web
python test_setup.py
```

Or using uvicorn directly from the project root:

```bash
uvicorn scraper.src.web.app:app --host 0.0.0.0 --port 8000 --reload
```

Or if you're in the scraper directory:

```bash
python -m src.web.app
```

Then open your browser to: http://localhost:8000

## Troubleshooting

If you get database connection errors:
1. Make sure PostgreSQL is running
2. Check that the database `bpo_intelligence` exists
3. Verify the password file is at `ops/secrets/postgres_password.txt` or the app will use default password "postgres"
4. Check database connection settings in the startup function

## Features

- **Organizations List**: View all organizations with summary statistics
- **Organization Detail**: View complete organization profile including:
  - Products
  - Services
  - Platforms
  - Certifications
  - Awards
  - Operating Markets
  - Relationships with other organizations
  - Linked corporate entities

- **Corporate Entities List**: View all corporate entities
- **Entity Detail**: View entity hierarchy (parents/children) and linked organizations

## API Endpoints

- `GET /` - Organizations list page
- `GET /organization/{org_id}` - Organization detail page
- `GET /entities` - Corporate entities list page
- `GET /entity/{entity_id}` - Entity detail page
- `GET /api/organizations` - JSON API for organizations list

