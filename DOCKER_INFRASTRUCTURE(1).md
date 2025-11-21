# Docker Infrastructure Documentation

Complete documentation of the BPO Intelligence web scraping system Docker infrastructure.

## Project Structure

```
NewPipeline/
├── data/                          # Host-mounted data directories
│   ├── logs/                      # Application logs
│   ├── postgres/                  # (Unused - postgres uses Docker volume)
│   ├── prefect/                   # Prefect server data
│   ├── redis/                     # Redis persistence data
│   └── scraped/                   # Scraped data output
├── ops/
│   └── secrets/                   # Docker secrets (gitignored)
│       ├── postgres_password.txt  # PostgreSQL password
│       └── apify_proxy_password.txt # Apify proxy password
└── scraper/                       # Main application directory
    ├── config/
    │   ├── bpo_sites.txt          # Target websites list
    │   └── scraper_config.yaml    # Scraper configuration
    ├── docker/
    │   ├── playwright/
    │   │   ├── Dockerfile         # Playwright browser pool image
    │   │   └── service.py         # FastAPI service for browser automation
    │   └── scraper-core/
    │       └── Dockerfile         # Main scraper application image
    ├── src/                       # Python source code
    │   ├── __init__.py
    │   ├── parsers/
    │   └── scrapers/
    ├── docker-compose.yml         # Main orchestration file
    ├── init-db.sql                # PostgreSQL initialization script
    └── requirements.txt           # Python dependencies
```

## Docker Services

### 1. PostgreSQL (bpo-postgres)

- **Image**: postgres:16-alpine
- **Container Name**: bpo-postgres
- **Hostname**: postgres
- **Port**: 5432 (exposed to host)
- **Database**: bpo_intelligence
- **User**: bpo_user
- **Password**: From secret file (`ops/secrets/postgres_password.txt`)
- **Volume**: 
  - `postgres-data:/var/lib/postgresql/data` (Docker volume, not host mount)
  - `./init-db.sql:/docker-entrypoint-initdb.d/init-db.sql:ro` (initialization script)
- **Network**: bpo-network
- **Secrets**: postgres_password
- **Health Check**: 
  - Command: `pg_isready -U bpo_user -d bpo_intelligence`
  - Interval: 10s
  - Timeout: 5s
  - Retries: 5
  - Start Period: 30s
- **Resources**: 
  - Limits: 2 CPU, 4GB RAM
  - Reservations: 1 CPU, 2GB RAM
- **Restart Policy**: unless-stopped

### 2. Redis (bpo-redis)

- **Image**: redis:7-alpine
- **Container Name**: bpo-redis
- **Hostname**: redis-scraper
- **Port**: 6379 (exposed to host)
- **Command**: 
  - `redis-server --appendonly yes --maxmemory 4gb --maxmemory-policy allkeys-lru --save 300 10 --tcp-backlog 511 --timeout 0 --tcp-keepalive 300 --maxclients 10000`
- **Volume**: `../data/redis:/data` (host mount for persistence)
- **Network**: bpo-network
- **Health Check**: 
  - Command: `redis-cli ping`
  - Interval: 10s
  - Timeout: 3s
  - Retries: 3
- **Resources**: 
  - Limits: 1 CPU, 8GB RAM
  - Reservations: 0.5 CPU, 4GB RAM
- **Restart Policy**: unless-stopped

### 3. Prefect Server (bpo-prefect-server)

- **Image**: prefecthq/prefect:3.1.9-python3.11
- **Container Name**: bpo-prefect-server
- **Hostname**: prefect-server
- **Port**: 4200 (exposed to host)
- **Command**: `prefect server start --host 0.0.0.0`
- **Environment Variables**:
  - `PREFECT_SERVER_API_HOST`: 0.0.0.0
  - `PREFECT_API_DATABASE_CONNECTION_URL`: postgresql+asyncpg://bpo_user:${POSTGRES_PASSWORD}@postgres:5432/bpo_intelligence
  - `PREFECT_API_URL`: http://0.0.0.0:4200/api
- **Volume**: `../data/prefect:/root/.prefect` (host mount)
- **Network**: bpo-network
- **Depends On**: postgres (condition: service_healthy)
- **Resources**: 
  - Limits: 1 CPU, 2GB RAM
- **Restart Policy**: unless-stopped

### 4. Scraper Core (bpo-scraper-core)

- **Image**: Built from `scraper/docker/scraper-core/Dockerfile`
- **Container Name**: bpo-scraper-core
- **Hostname**: scraper-core
- **Base Image**: python:3.11-slim (multi-stage build)
- **User**: scraper (UID 1000)
- **Volumes**:
  - `./src:/app/src:ro` (read-only source code)
  - `./config:/app/config:ro` (read-only configuration)
  - `../data/scraped:/app/data:rw` (output data)
  - `../data/logs:/app/logs:rw` (application logs)
- **Environment Variables**:
  - Database: `POSTGRES_HOST=postgres`, `POSTGRES_DB=bpo_intelligence`, `POSTGRES_USER=bpo_user`, `POSTGRES_PASSWORD_FILE=/run/secrets/postgres_password`
  - Redis: `REDIS_HOST=redis-scraper`, `REDIS_PORT=6379`
  - Prefect: `PREFECT_API_URL=http://prefect-server:4200/api`
  - Apify: `APIFY_PROXY_PASSWORD_FILE=/run/secrets/apify_proxy_password`
  - Scraper: `LOG_LEVEL=INFO`, `RATE_LIMIT=5`, `MAX_CONCURRENT=10`, `OUTPUT_DIR=/app/data`
- **Network**: bpo-network
- **Secrets**: postgres_password, apify_proxy_password
- **Depends On**: 
  - postgres (condition: service_healthy)
  - redis (condition: service_healthy)
  - prefect-server (condition: service_started)
- **Health Check**: 
  - Command: `python -c "import sys; sys.exit(0)"`
  - Interval: 30s
  - Timeout: 10s
  - Retries: 3
  - Start Period: 60s
- **Resources**: 
  - Limits: 4 CPU, 16GB RAM
  - Reservations: 2 CPU, 8GB RAM
- **CMD**: `tail -f /dev/null` (keeps container running for manual/Prefect-triggered workflows)
- **Restart Policy**: unless-stopped

### 5. Playwright Pool (scraper-playwright-pool-1, scraper-playwright-pool-2)

- **Image**: Built from `scraper/docker/playwright/Dockerfile`
- **Container Names**: scraper-playwright-pool-1, scraper-playwright-pool-2
- **Hostname**: playwright-pool
- **Base Image**: mcr.microsoft.com/playwright/python:v1.48.0-jammy
- **Replicas**: 2
- **Port**: 3000 (internal, not exposed to host)
- **User**: UID 1000 (handles existing user in base image)
- **Environment Variables**:
  - `PLAYWRIGHT_BROWSERS_PATH`: /ms-playwright
- **Volumes**:
  - `playwright-browsers:/ms-playwright:rw` (shared browser cache)
- **Network**: bpo-network
- **SHM Size**: 4GB
- **Service**: FastAPI with `/health` endpoint
- **Health Check**: 
  - Command: `curl -f http://localhost:3000/health`
  - Interval: 30s
  - Timeout: 10s
  - Retries: 3
  - Start Period: 30s
- **CMD**: `uvicorn service:app --host 0.0.0.0 --port 3000 --workers 2`
- **Resources**: 
  - Limits: 1.5 CPU, 6GB RAM
  - Reservations: 1 CPU, 4GB RAM
- **Restart Policy**: unless-stopped

## Docker Networks

### bpo-network

- **Type**: Bridge network
- **Name**: bpo-network
- **Subnet**: 172.28.0.0/16
- **Connected Services**: All services (postgres, redis, prefect-server, scraper-core, playwright-pool)

## Docker Volumes

### 1. playwright-browsers

- **Name**: playwright-browsers
- **Type**: Named volume
- **Purpose**: Shared browser binaries and cache between Playwright pool replicas
- **Mount Point**: `/ms-playwright` in playwright-pool containers

### 2. postgres-data

- **Name**: bpo-postgres-data
- **Type**: Named volume
- **Purpose**: PostgreSQL database data persistence
- **Mount Point**: `/var/lib/postgresql/data` in postgres container
- **Note**: Uses Docker volume instead of host mount to avoid Windows mount issues

## Docker Secrets

### 1. postgres_password

- **Source**: `../ops/secrets/postgres_password.txt` (relative to docker-compose.yml)
- **Mount Point**: `/run/secrets/postgres_password` in containers
- **Used By**: postgres, scraper-core
- **Current Value**: `bpo_secure_password_2025` (default, should be changed in production)

### 2. apify_proxy_password

- **Source**: `../ops/secrets/apify_proxy_password.txt` (relative to docker-compose.yml)
- **Mount Point**: `/run/secrets/apify_proxy_password` in containers
- **Used By**: scraper-core
- **Current Value**: `YOUR_APIFY_PASSWORD_HERE` (placeholder, must be updated)

## Key Configuration Details

### Python Dependencies (requirements.txt)

#### Core Scraping
- `curl-cffi==0.6.2` - HTTP client with TLS fingerprinting
- `beautifulsoup4==4.12.3` - HTML parsing
- `lxml==5.3.0` - XML/HTML parser

#### Playwright (for Tier 2/3)
- `playwright==1.48.0` - Browser automation
- `playwright-stealth==1.0.5` - Stealth mode for Playwright

#### Apify Integration
- `apify-client==1.7.1` - Apify proxy client (fixed from 1.7.2)

#### Data Processing
- `pandas==2.2.3` - Data manipulation
- `pydantic==2.9.2` - Data validation
- `python-dateutil==2.9.0` - Date parsing

#### Orchestration
- `prefect==3.1.9` - Workflow orchestration
- `redis==5.2.0` - Redis client
- `psycopg[binary]==3.2.3` - PostgreSQL adapter

#### Reliability
- `tenacity==9.0.0` - Retry logic
- `ratelimit==2.2.1` - Rate limiting

#### Utilities
- `python-dotenv==1.0.1` - Environment variable management
- `loguru==0.7.3` - Logging
- `pyyaml==6.0.2` - YAML parsing

#### Testing
- `pytest==8.3.4` - Testing framework
- `pytest-asyncio==0.24.0` - Async testing support

### Dockerfile Details

#### Scraper Core Dockerfile

- **Multi-stage build** for efficient image size
- **Builder stage**: Installs build dependencies (gcc, g++, make, libpq-dev)
- **Runtime stage**: Only runtime dependencies (libpq5)
- **Virtual environment**: Created in builder, copied to runtime
- **Non-root user**: `scraper` (UID 1000)
- **Working directory**: `/app`
- **Health check**: Simple Python import test

#### Playwright Dockerfile

- **Base image**: Microsoft Playwright Python image (includes browsers)
- **Additional packages**: curl (for health checks)
- **Python packages**: FastAPI, uvicorn, playwright, playwright-stealth
- **User handling**: Checks for existing UID 1000 before creating user
- **Service**: FastAPI application on port 3000
- **Health check**: HTTP endpoint check

### Important Fixes Applied

1. **apify-client version correction**: Changed from `1.7.2` (non-existent) to `1.7.1` (latest stable)
2. **Playwright Dockerfile user creation**: Added logic to handle existing UID 1000 user in base image
3. **PostgreSQL volume configuration**: Changed from host mount (`../data/postgres:/var/lib/postgresql/data`) to Docker volume (`postgres-data`) to fix Windows mount point issues that prevented database initialization

## Access Points

- **Prefect UI**: http://localhost:4200
- **PostgreSQL**: localhost:5432
  - Database: `bpo_intelligence`
  - User: `bpo_user`
  - Password: From `ops/secrets/postgres_password.txt`
- **Redis**: localhost:6379
- **Playwright Health**: Internal port 3000 (not exposed to host)

## Build and Management Commands

### Build Images

```bash
cd scraper
docker-compose build                    # Build all custom images
docker-compose build scraper-core       # Build only scraper-core
docker-compose build playwright-pool    # Build only playwright-pool
```

### Start Services

```bash
cd scraper
docker-compose up -d                    # Start all services in detached mode
docker-compose up -d postgres redis     # Start specific services
```

### Check Status

```bash
cd scraper
docker-compose ps                       # List all services and their status
docker-compose ps --format json         # JSON format
docker ps                               # List all containers
docker-compose logs                     # View logs from all services
docker-compose logs scraper-core        # View logs from specific service
docker-compose logs -f                  # Follow logs in real-time
```

### Stop Services

```bash
cd scraper
docker-compose stop                     # Stop all services (keeps containers)
docker-compose down                     # Stop and remove containers (keeps volumes)
docker-compose down -v                  # Stop and remove containers and volumes
```

### Scale Services

```bash
cd scraper
docker-compose up -d --scale playwright-pool=5    # Scale playwright-pool to 5 replicas
docker-compose up -d --scale playwright-pool=2    # Scale back to 2 replicas
```

### Access Containers

```bash
docker exec -it bpo-scraper-core bash              # Access scraper-core container
docker exec -it bpo-postgres psql -U bpo_user -d bpo_intelligence  # Access PostgreSQL
docker exec -it bpo-redis redis-cli                # Access Redis CLI
```

### Database Operations

```bash
# Backup database
docker exec bpo-postgres pg_dump -U bpo_user bpo_intelligence > backup.sql

# Restore database
cat backup.sql | docker exec -i bpo-postgres psql -U bpo_user -d bpo_intelligence

# Access database
docker exec -it bpo-postgres psql -U bpo_user -d bpo_intelligence
```

## Current Status

All containers are running and healthy:

- ✅ **bpo-postgres**: Healthy (PostgreSQL 16)
- ✅ **bpo-redis**: Healthy (Redis 7)
- ✅ **bpo-prefect-server**: Running (Prefect 3.1.9)
- ✅ **bpo-scraper-core**: Healthy (Python 3.11)
- ✅ **scraper-playwright-pool-1**: Healthy (Playwright 1.48.0)
- ✅ **scraper-playwright-pool-2**: Healthy (Playwright 1.48.0)

## Resource Requirements

### Minimum System Requirements

- **CPU**: 4 cores
- **RAM**: 16GB
- **Disk**: 50GB free space

### Recommended System Requirements

- **CPU**: 8+ cores
- **RAM**: 32GB+
- **Disk**: 100GB+ free space

### Expected Resource Usage (Idle)

| Service | CPU | Memory |
|---------|-----|--------|
| bpo-postgres | 0.1% | ~200MB |
| bpo-redis | 0.1% | ~4GB |
| bpo-prefect-server | 0.2% | ~500MB |
| bpo-scraper-core | 0.0% | ~200MB |
| scraper-playwright-pool-1 | 0.1% | ~2GB |
| scraper-playwright-pool-2 | 0.1% | ~2GB |
| **Total** | **~0.6%** | **~9GB** |

## Troubleshooting

### PostgreSQL Won't Start

**Issue**: Container keeps restarting with "directory exists but is not empty" error.

**Solution**: Use Docker volume instead of host mount (already fixed in current configuration).

### Secrets Not Found

**Issue**: Services fail with "secret not found" errors.

**Solution**: Ensure secret files exist at:
- `ops/secrets/postgres_password.txt`
- `ops/secrets/apify_proxy_password.txt`

### Port Already in Use

**Issue**: Error binding to ports 5432, 6379, or 4200.

**Solution**: Change port mappings in `docker-compose.yml` or stop conflicting services.

### Playwright Pool Health Check Fails

**Issue**: Playwright containers show as unhealthy.

**Solution**: Check logs with `docker-compose logs playwright-pool`. Ensure FastAPI service is running on port 3000.

## Security Notes

- Secrets are stored in `ops/secrets/` and mounted as Docker secrets (not environment variables)
- The `.gitignore` file prevents secrets from being committed to version control
- All containers run as non-root users (UID 1000)
- Database is only exposed to localhost (not internet)
- Secrets are read-only mounted at `/run/secrets/` in containers

## Next Steps

1. **Update Apify Password**: Edit `ops/secrets/apify_proxy_password.txt` with actual password
2. **Configure Scraper**: Edit `scraper/config/scraper_config.yaml` for scraper settings
3. **Add Target Sites**: Edit `scraper/config/bpo_sites.txt` with target URLs
4. **Implement Scraper Code**: Add Python code in `scraper/src/` directories
5. **Test Workflows**: Use Prefect UI to create and test scraping workflows

