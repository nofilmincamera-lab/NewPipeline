# Complete Docker Infrastructure Setup Guide

## Overview

This guide provides step-by-step instructions for setting up the complete Docker infrastructure for the BPO Intelligence web scraping system.

## ✅ Installation Checklist

### Phase 1: Infrastructure Files (COMPLETED)

All infrastructure files have been created:

- [x] Complete directory structure
- [x] Docker Compose configuration
- [x] Database initialization script
- [x] Scraper-core Dockerfile
- [x] Playwright Dockerfile and service
- [x] Requirements.txt
- [x] Configuration files (YAML, sites list)
- [x] Environment file
- [x] .gitignore
- [x] Python package __init__.py files

### Phase 2: Configuration (REQUIRED BEFORE STARTING)

Before starting the services, you must:

1. **Update Apify Proxy Password**
   ```bash
   # Replace with your actual password
   echo -n "YOUR_ACTUAL_APIFY_PASSWORD" > ops/secrets/apify_proxy_password.txt
   ```

2. **Update BPO Sites List**
   ```bash
   # Edit with your 60+ target websites
   nano scraper/config/bpo_sites.txt
   ```

3. **Optional: Adjust Configuration**
   ```bash
   # Edit scraper settings if needed
   nano scraper/config/scraper_config.yaml
   ```

### Phase 3: Build and Start Services

```bash
cd scraper

# Build all images (first time: 5-10 minutes)
docker-compose build

# Start all services
docker-compose up -d

# Check status (all should show "healthy")
docker-compose ps
```

### Phase 4: Verify Each Service

#### PostgreSQL
```bash
docker exec -it bpo-postgres psql -U bpo_user -d bpo_intelligence -c "\dt"
```
Expected: Should list tables (scraped_sites, domain_proxy_requirements, proxy_usage_log)

#### Redis
```bash
docker exec -it bpo-redis redis-cli ping
```
Expected: PONG

#### Prefect
```bash
# Check if service is running
curl http://localhost:4200/api/health
```
Expected: HTTP 200 response

#### Scraper Core
```bash
docker exec -it bpo-scraper-core python --version
docker exec -it bpo-scraper-core pip list | grep curl-cffi
```
Expected: Python 3.11.x, curl-cffi==0.6.2

#### Playwright
```bash
curl http://localhost:3000/health
```
Expected: {"status":"healthy",...}

### Phase 5: Test Connections

Run this comprehensive test:

```bash
docker exec -it bpo-scraper-core bash -c '
echo "Testing Python imports..."
python -c "from curl_cffi.requests import Session; print(\"✓ curl_cffi works\")"

echo "Testing database connection..."
python -c "
import asyncpg
import asyncio

async def test():
    conn = await asyncpg.connect(
        host=\"postgres\",
        database=\"bpo_intelligence\",
        user=\"bpo_user\",
        password=open(\"/run/secrets/postgres_password\").read().strip()
    )
    print(\"✓ Database connected\")
    await conn.close()

asyncio.run(test())
"

echo "Testing Redis connection..."
python -c "
import redis
r = redis.Redis(host=\"redis-scraper\", port=6379)
r.ping()
print(\"✓ Redis connected\")
"

echo "All tests passed!"
'
```

## Services Overview

Once running, you'll have:

| Service | Container Name | Port | Purpose |
|---------|---------------|------|---------|
| PostgreSQL | bpo-postgres | 5432 | Main database |
| Redis | bpo-redis | 6379 | Caching & queues |
| Prefect | bpo-prefect-server | 4200 | Workflow orchestration |
| Scraper Core | bpo-scraper-core | - | Main scraping app |
| Playwright Pool | playwright-pool-1,2 | 3000 | Browser automation |

## Resource Requirements

**Minimum (Tier 1):**
- CPU: 4 cores
- RAM: 16GB
- Disk: 50GB

**Recommended:**
- CPU: 8+ cores
- RAM: 32GB+
- Disk: 100GB+

**Your System:**
- CPU: Intel Core Ultra 9 285K (excellent!)
- RAM: 128GB (more than enough!)
- Network: 3Gbps (excellent!)

## Expected Resource Usage (Idle)

```
SERVICE              CPU%    MEM USAGE
bpo-postgres         0.1%    ~200MB
bpo-redis            0.1%    ~4GB
bpo-prefect-server   0.2%    ~500MB
bpo-scraper-core     0.0%    ~200MB
playwright-pool-1    0.1%    ~2GB
playwright-pool-2    0.1%    ~2GB
--------------------------------
TOTAL                        ~9GB
```

## Common Issues and Solutions

### Issue: Port Already in Use

**Error:** `Bind for 0.0.0.0:5432 failed: port is already allocated`

**Solution:** Change the port mapping in docker-compose.yml:
```yaml
ports:
  - "15432:5432"  # Use different host port
```

### Issue: Out of Memory

**Error:** `Cannot allocate memory`

**Solution:** Adjust resource limits in docker-compose.yml or increase Docker's memory allocation.

### Issue: Permission Denied on Volumes

**Error:** `mkdir: cannot create directory: Permission denied`

**Solution:**
```bash
sudo chown -R $USER:$USER data/
```

### Issue: Database Initialization Failed

**Error:** `psql: FATAL: password authentication failed`

**Solution:**
```bash
# Verify password file
cat ops/secrets/postgres_password.txt

# Ensure no newline at end
echo -n "bpo_secure_password_2025" > ops/secrets/postgres_password.txt

# Restart
docker-compose restart postgres
```

## Scaling Guide

### Scale Playwright Pool

For high-volume scraping:

```bash
# Scale to 10 instances
docker-compose up -d --scale playwright-pool=10

# Monitor resources
docker stats
```

### Increase Database Resources

Edit docker-compose.yml:

```yaml
postgres:
  deploy:
    resources:
      limits:
        cpus: '4'      # Increase from 2
        memory: 8G     # Increase from 4G
```

## Monitoring

### View Live Logs

```bash
# All services
docker-compose logs -f

# Single service
docker-compose logs -f scraper-core

# Last 100 lines
docker-compose logs --tail=100 scraper-core
```

### Check Resource Usage

```bash
# Real-time stats
docker stats

# One-time check
docker stats --no-stream
```

### Database Queries

```bash
docker exec -it bpo-postgres psql -U bpo_user -d bpo_intelligence

# Inside psql:
SELECT * FROM scraping_stats;
SELECT COUNT(*) FROM scraped_sites;
SELECT domain, COUNT(*) FROM scraped_sites GROUP BY domain;
```

## Backup and Recovery

### Backup Database

```bash
docker exec bpo-postgres pg_dump -U bpo_user bpo_intelligence > backup.sql
```

### Restore Database

```bash
cat backup.sql | docker exec -i bpo-postgres psql -U bpo_user -d bpo_intelligence
```

### Backup All Data

```bash
tar -czf bpo-backup-$(date +%Y%m%d).tar.gz data/
```

## Shutdown Procedures

### Graceful Shutdown

```bash
# Stop all services (keeps data)
docker-compose stop

# Or stop and remove containers (keeps volumes)
docker-compose down
```

### Complete Cleanup

```bash
# WARNING: This removes ALL data!
docker-compose down -v

# Remove images too
docker-compose down -v --rmi all
```

## Next Steps

After verifying all services are running:

1. **Implement Scraper Code**
   - The infrastructure is ready
   - Start implementing Python code in `scraper/src/`
   - Use the provided guide for Tier 1 scraper implementation

2. **Test with Sample Sites**
   - Start with 5-10 sites
   - Verify data is saved to database
   - Check logs for errors

3. **Scale Up**
   - Once working, add all 60+ sites
   - Scale Playwright pool as needed
   - Monitor resource usage

4. **Set Up Monitoring**
   - Use Prefect UI for workflow monitoring
   - Check database stats regularly
   - Monitor Redis cache hit rates

## Support Resources

- **Docker Compose Reference**: https://docs.docker.com/compose/
- **PostgreSQL Docs**: https://www.postgresql.org/docs/
- **Redis Docs**: https://redis.io/docs/
- **Prefect Docs**: https://docs.prefect.io/

## Summary

✅ **What You Have:**
- Complete Docker infrastructure
- All services configured and ready
- Database initialized with tables
- Secrets properly mounted
- Configuration files ready

🔄 **What's Next:**
1. Update Apify password
2. Add your BPO sites list
3. Start services with `docker-compose up -d`
4. Verify all services are healthy
5. Implement scraper Python code

🚀 **You're ready to build!**
