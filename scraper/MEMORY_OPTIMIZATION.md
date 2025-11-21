# Memory Optimization Summary

Memory allocations have been increased across all services to improve performance and handle larger workloads.

## Memory Allocation Changes

### PostgreSQL Database
- **Previous**: 4GB limit, 2GB reservation
- **Updated**: 8GB limit, 4GB reservation
- **Benefit**: Better query performance, larger result sets, improved caching

### Redis Cache
- **Previous**: 8GB limit, 4GB reservation, 4GB maxmemory
- **Updated**: 16GB limit, 8GB reservation, 12GB maxmemory
- **Benefit**: Larger cache capacity, more concurrent operations, better performance

### Scraper Core
- **Previous**: 16GB limit, 8GB reservation
- **Updated**: 32GB limit, 16GB reservation
- **Benefit**: Handle more concurrent scraping operations, larger data processing

### Playwright Browser Pool
- **Previous**: 6GB limit, 4GB reservation per replica, 4GB shared memory
- **Updated**: 12GB limit, 8GB reservation per replica, 8GB shared memory
- **Benefit**: More browser instances, better performance for JavaScript-heavy sites

## Concurrency Increases

### Scraper Workers
- **Previous**: 10 parallel workers
- **Updated**: 20 parallel workers
- **Benefit**: 2x throughput for scraping operations

### Playwright Workers
- **Previous**: 2 uvicorn workers per replica
- **Updated**: 4 uvicorn workers per replica
- **Benefit**: Better handling of concurrent browser requests

### MAX_CONCURRENT
- **Previous**: 10
- **Updated**: 20
- **Benefit**: More concurrent operations in scraper-core container

## Total Memory Usage

### Per Service (Idle)
| Service | Memory Limit | Memory Reservation |
|---------|--------------|-------------------|
| PostgreSQL | 8GB | 4GB |
| Redis | 16GB | 8GB |
| Scraper Core | 32GB | 16GB |
| Playwright (per replica) | 12GB | 8GB |
| **Total (2 Playwright replicas)** | **80GB** | **44GB** |

### Under Load
- **Expected peak usage**: ~60-70GB
- **Recommended system RAM**: 64GB+ for optimal performance
- **Minimum system RAM**: 32GB (with swap)

## Prefect Server (WSL2)

Prefect Server running in WSL2 can use system memory as needed. Recommended:
- **Minimum**: 2GB available
- **Recommended**: 4GB+ available
- **Peak usage**: Up to 4GB during heavy workflow execution

## Performance Impact

### Expected Improvements
1. **2x faster scraping** - More parallel workers
2. **Better cache hit rates** - Larger Redis cache
3. **Faster database queries** - More PostgreSQL memory for caching
4. **More browser instances** - Increased Playwright capacity
5. **Reduced OOM errors** - Higher memory limits prevent crashes

### Monitoring

Monitor memory usage with:
```bash
# Docker container memory
docker stats

# WSL2 memory (for Prefect)
free -h

# System memory
# Windows: Task Manager
# Linux: htop or top
```

## Adjusting Memory

If you need to adjust memory allocations:

1. **Edit docker-compose.yml** - Modify `memory` values in `deploy.resources`
2. **Edit Redis maxmemory** - Update `--maxmemory` in redis command
3. **Edit worker counts** - Update `PARALLEL_WORKERS` and `MAX_CONCURRENT`
4. **Restart services**:
   ```bash
   docker-compose down
   docker-compose up -d
   ```

## Notes

- Memory limits are maximums - containers only use what they need
- Reservations guarantee minimum memory allocation
- If system has less RAM, Docker will use swap (slower)
- Monitor actual usage and adjust based on workload

