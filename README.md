# BPO Intelligence Web Scraper

Complete, production-ready web scraping system with Docker infrastructure.

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Complete Scraping System (All in Docker)                   │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ PostgreSQL   │  │ Redis        │  │ Prefect      │     │
│  │ (Database)   │  │ (Cache)      │  │ (Orchestr.)  │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐                       │
│  │ Scraper-Core │  │ Playwright   │                       │
│  │ (Main app)   │  │ (Browsers)   │                       │
│  └──────────────┘  └──────────────┘                       │
└─────────────────────────────────────────────────────────────┘
```

## Prerequisites

- Docker Engine 20.10+ and Docker Compose v2.0+
- At least 16GB RAM available (32GB+ recommended)
- 50GB+ free disk space
- Apify proxy account (optional, for proxy features)

## Quick Start

### 1. Update Secrets

Before starting, update your Apify proxy password:

```bash
echo -n "YOUR_ACTUAL_APIFY_PASSWORD" > ops/secrets/apify_proxy_password.txt
```

### 2. Build and Start Services

```bash
cd scraper
docker-compose build
docker-compose up -d
```

### 3. Verify Services

```bash
# Check all services are healthy
docker-compose ps

# Expected output: All services should show "Up (healthy)"
```

### 4. Access Services

- **Prefect UI**: http://localhost:4200
- **PostgreSQL**: localhost:5432 (user: bpo_user, db: bpo_intelligence)
- **Redis**: localhost:6379
- **Playwright Health**: http://localhost:3000/health

## Project Structure

```
.
├── scraper/                    # Main scraper application
│   ├── docker/                 # Dockerfiles
│   │   ├── scraper-core/
│   │   │   └── Dockerfile
│   │   └── playwright/
│   │       ├── Dockerfile
│   │       └── service.py
│   ├── src/                    # Python source code
│   │   ├── __init__.py
│   │   ├── scrapers/
│   │   │   └── __init__.py
│   │   └── parsers/
│   │       └── __init__.py
│   ├── config/                 # Configuration
│   │   ├── scraper_config.yaml
│   │   └── bpo_sites.txt
│   ├── requirements.txt
│   ├── init-db.sql
│   ├── docker-compose.yml
│   └── .env
├── data/                       # Data storage (host-mounted)
│   ├── scraped/
│   ├── postgres/
│   ├── redis/
│   ├── prefect/
│   └── logs/
└── ops/
    └── secrets/                # Credentials
        ├── postgres_password.txt
        └── apify_proxy_password.txt
```

## Configuration

### Database Configuration

PostgreSQL is initialized with the following tables:
- `scraped_sites` - Main scraping results
- `domain_proxy_requirements` - Proxy decision tracking
- `proxy_usage_log` - Proxy usage analytics

### Scraper Configuration

Edit `scraper/config/scraper_config.yaml` to adjust:
- Rate limiting
- Proxy strategy (never/always/intelligent)
- Timeouts and retries
- Content limits

### BPO Sites List

Edit `scraper/config/bpo_sites.txt` to add your target websites (one URL per line).

## Common Operations

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f scraper-core
```

### Access Scraper Container

```bash
docker exec -it bpo-scraper-core bash
```

### Database Access

```bash
docker exec -it bpo-postgres psql -U bpo_user -d bpo_intelligence
```

### Redis CLI

```bash
docker exec -it bpo-redis redis-cli
```

### Scale Playwright Pool

```bash
# Scale to 10 instances
docker-compose up -d --scale playwright-pool=10

# Scale back to 2
docker-compose up -d --scale playwright-pool=2
```

### Restart Services

```bash
# Restart all
docker-compose restart

# Restart specific service
docker-compose restart scraper-core
```

### Stop Everything

```bash
# Stop (keeps data)
docker-compose down

# Stop and remove all data (destructive!)
docker-compose down -v
```

## Testing Database Connection

```bash
docker exec -it bpo-scraper-core python -c "
import asyncpg
import asyncio

async def test():
    conn = await asyncpg.connect(
        host='postgres',
        database='bpo_intelligence',
        user='bpo_user',
        password=open('/run/secrets/postgres_password').read().strip()
    )
    result = await conn.fetch('SELECT COUNT(*) FROM scraped_sites')
    print(f'✓ Database connected. Scraped sites: {result[0][0]}')
    await conn.close()

asyncio.run(test())
"
```

## Resource Monitoring

```bash
# Monitor resource usage
docker stats

# Expected idle usage:
# - PostgreSQL:      ~200MB RAM
# - Redis:           ~4GB RAM
# - Prefect:         ~500MB RAM
# - Scraper Core:    ~200MB RAM
# - Playwright Pool: ~2GB RAM each
```

## Troubleshooting

### Port Already in Use

If ports 5432, 6379, or 4200 are already in use, edit `docker-compose.yml` to change the port mappings.

### Container Won't Start

```bash
# Check logs
docker-compose logs [service-name]

# Rebuild without cache
docker-compose build --no-cache [service-name]
```

### Database Connection Issues

```bash
# Verify password file
docker exec -it bpo-scraper-core cat /run/secrets/postgres_password

# Test direct connection
docker exec -it bpo-postgres psql -U bpo_user -d bpo_intelligence
```

### Out of Disk Space

```bash
# Clean up unused Docker resources
docker system prune -a --volumes

# Warning: This removes ALL unused containers, images, and volumes
```

## Security Notes

- Secrets are stored in `ops/secrets/` and mounted as Docker secrets
- The `.gitignore` file prevents secrets from being committed
- All containers run as non-root users
- Database is not exposed to the internet (localhost only)

## Next Steps

After the infrastructure is running:

1. **Implement Python scraping code** in `scraper/src/`
2. **Test the scraper** with a small subset of sites
3. **Monitor logs** and metrics in Prefect UI
4. **Scale up** Playwright pool as needed

## Support

For issues or questions:
- Check container logs: `docker-compose logs [service-name]`
- Verify all services are healthy: `docker-compose ps`
- Review this README and configuration files

## License

Proprietary - BPO Intelligence Project
