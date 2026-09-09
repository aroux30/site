# Troubleshooting Guide

## Overview

This guide covers common issues, their symptoms, and how to resolve them.

---

## Docker and Container Issues

### Containers fail to start

**Symptoms:** `docker compose up` exits with errors; services show as "Exited" in `docker compose ps`.

**Diagnosis:**
```bash
# Check which containers are failing
docker compose ps

# Check container logs
docker compose logs <service-name>

# Check Docker daemon logs
sudo journalctl -u docker --since "1 hour ago"
```

**Common causes and fixes:**

1. **Port already in use:**
   ```bash
   # Find what's using the port
   sudo lsof -i :8000
   # Kill the process or change the port in docker-compose.yml
   ```

2. **Insufficient disk space:**
   ```bash
   df -h
   # Clean up Docker resources
   docker system prune -a --volumes
   ```

3. **Invalid environment variables:**
   ```bash
   # Validate .env file
   cat .env | grep -v '^#' | grep -v '^$'
   ```

### Container keeps restarting

**Symptoms:** Container status shows "Restarting" in a loop.

**Diagnosis:**
```bash
docker compose logs --tail=50 <service-name>
docker inspect <container-id> | grep -A 10 "State"
```

**Common causes:**
- Application crash on startup (check logs for stack traces)
- Database not ready (check depends_on and health checks)
- Missing required environment variables

---

## Database Issues

### Cannot connect to PostgreSQL

**Symptoms:** Application logs show "connection refused" or "could not connect to server".

**Diagnosis:**
```bash
# Check if PostgreSQL container is running
docker compose ps postgres

# Check PostgreSQL logs
docker compose logs postgres

# Test connection from inside the network
docker compose exec backend python -c "
import psycopg2
conn = psycopg2.connect(host='postgres', dbname='app_db', user='app_user', password='your_password')
print('Connected successfully')
conn.close()
"
```

**Fixes:**
1. Ensure the PostgreSQL container is healthy:
   ```bash
   docker compose exec postgres pg_isready -U app_user
   ```

2. Check credentials in `.env` match what PostgreSQL was initialized with.

3. If credentials changed, recreate the database volume:
   ```bash
   docker compose down -v  # WARNING: destroys data
   docker compose up -d
   ```

### Database out of disk space

**Symptoms:** Write operations fail; logs show "No space left on device".

**Diagnosis:**
```bash
# Check disk usage
df -h

# Check database size
docker compose exec postgres psql -U app_user -d app_db -c "
  SELECT pg_size_pretty(pg_database_size('app_db'));
"
```

**Fixes:**
1. Clean up old data or run VACUUM:
   ```bash
   docker compose exec postgres psql -U app_user -d app_db -c "VACUUM FULL;"
   ```

2. Remove old Docker volumes and images:
   ```bash
   docker system prune --volumes
   ```

3. Expand disk storage on the server.

### Slow database queries

**Symptoms:** Application responds slowly; timeout errors in logs.

**Diagnosis:**
```bash
# Check active queries
docker compose exec postgres psql -U app_user -d app_db -c "
  SELECT pid, now() - pg_stat_activity.query_start AS duration, query, state
  FROM pg_stat_activity
  WHERE state != 'idle'
  ORDER BY duration DESC;
"

# Check for missing indexes
docker compose exec postgres psql -U app_user -d app_db -c "
  SELECT relname, seq_scan, idx_scan
  FROM pg_stat_user_tables
  WHERE seq_scan > 1000
  ORDER BY seq_scan DESC
  LIMIT 10;
"
```

**Fixes:**
- Add indexes for frequently queried columns.
- Run `VACUUM ANALYZE` to update query planner statistics.
- Kill long-running queries:
  ```bash
  docker compose exec postgres psql -U app_user -d app_db -c "
    SELECT pg_terminate_backend(<pid>);
  "
  ```

---

## Application Issues

### 502 Bad Gateway

**Symptoms:** Nginx returns 502 errors.

**Diagnosis:**
```bash
# Check if backend is running
docker compose ps backend

# Check backend logs
docker compose logs --tail=50 backend

# Check Nginx logs
docker compose logs --tail=50 nginx

# Test backend health directly
docker compose exec backend curl -s http://localhost:8000/api/health/
```

**Fixes:**
1. Restart the backend service:
   ```bash
   docker compose restart backend
   ```

2. Check if the backend is listening on the expected port.

3. Verify Nginx upstream configuration matches the backend container name and port.

### High memory usage

**Symptoms:** Server becomes unresponsive; OOM killer terminates processes.

**Diagnosis:**
```bash
# Check overall memory
free -h

# Check per-container memory usage
docker stats --no-stream

# Check for memory leaks in backend
docker compose exec backend python -c "
import tracemalloc
tracemalloc.start()
# ... application snapshot
"
```

**Fixes:**
1. Set memory limits in `docker-compose.yml`:
   ```yaml
   services:
     backend:
       deploy:
         resources:
           limits:
             memory: 512M
   ```

2. Restart the offending service:
   ```bash
   docker compose restart <service-name>
   ```

3. Increase server memory.

### Static files not loading (404)

**Symptoms:** CSS, JS, and images return 404 errors.

**Diagnosis:**
```bash
# Check if static files are collected
docker compose exec backend ls -la /app/static/

# Check Nginx static file configuration
docker compose exec nginx cat /etc/nginx/conf.d/default.conf | grep -A 5 "location /static"
```

**Fixes:**
1. Collect static files:
   ```bash
   docker compose exec backend python manage.py collectstatic --noinput
   ```

2. Verify the static files volume is correctly mounted in both the backend and Nginx containers.

---

## Deployment Issues

### Deployment fails at health check

**Symptoms:** Deployment script reports health check failures; automatic rollback triggers.

**Diagnosis:**
```bash
# Check if the health endpoint is responding
curl -v http://localhost:8000/api/health/

# Check backend logs during startup
docker compose logs --tail=100 backend
```

**Fixes:**
1. Ensure the health check endpoint exists and returns HTTP 200.
2. Increase health check retries/timeout in `scripts/deploy.sh`.
3. Check if migrations are blocking startup.

### Git pull fails during deployment

**Symptoms:** Deployment fails at the "pull latest code" step.

**Diagnosis:**
```bash
cd /opt/app
git status
git remote -v
```

**Fixes:**
1. If there are local changes:
   ```bash
   git stash
   git pull
   git stash pop
   ```

2. If there are merge conflicts:
   ```bash
   git reset --hard origin/main
   ```

### Docker build fails

**Symptoms:** `docker compose build` exits with errors.

**Diagnosis:**
```bash
# Build with verbose output
docker compose build --no-cache --progress=plain <service-name>
```

**Common causes:**
- Network issues downloading dependencies (retry or check DNS)
- Package version conflicts (review Dockerfile and requirements)
- Insufficient disk space for build layers

---

## Network Issues

### DNS resolution failures

**Symptoms:** Containers cannot resolve external hostnames.

**Diagnosis:**
```bash
# Test DNS from inside a container
docker compose exec backend nslookup google.com

# Check Docker DNS configuration
docker network inspect bridge | grep -A 5 "IPAM"
```

**Fixes:**
1. Add DNS configuration to `docker-compose.yml`:
   ```yaml
   services:
     backend:
       dns:
         - 8.8.8.8
         - 8.8.4.4
   ```

2. Restart the Docker daemon:
   ```bash
   sudo systemctl restart docker
   ```

### Redis connection failures

**Symptoms:** Application logs show Redis connection errors or timeouts.

**Diagnosis:**
```bash
# Check Redis container
docker compose ps redis

# Test Redis connectivity
docker compose exec redis redis-cli ping
# Expected: PONG

# Check Redis memory
docker compose exec redis redis-cli info memory | grep used_memory_human
```

**Fixes:**
1. Restart Redis:
   ```bash
   docker compose restart redis
   ```

2. Check `REDIS_URL` in `.env` matches the container service name.

---

## Performance Issues

### Identifying bottlenecks

```bash
# System overview
htop

# Container resource usage
docker stats

# Disk I/O
iostat -x 1 5

# Network connections
ss -tlnp
```

### Quick performance fixes

1. **Restart all services:** `docker compose restart`
2. **Clear Redis cache:** `docker compose exec redis redis-cli FLUSHALL`
3. **Vacuum database:** `docker compose exec postgres psql -U app_user -d app_db -c "VACUUM ANALYZE;"`
4. **Prune Docker resources:** `docker system prune -f`

---

## Getting Help

If the above steps do not resolve your issue:

1. Collect diagnostic information:
   ```bash
   docker compose ps > /tmp/diag_ps.txt
   docker compose logs --tail=500 > /tmp/diag_logs.txt 2>&1
   docker stats --no-stream > /tmp/diag_stats.txt
   df -h > /tmp/diag_disk.txt
   free -h > /tmp/diag_memory.txt
   ```

2. Check the deployment logs in `./logs/deploy_*.log`.

3. Review recent commits for potential breaking changes:
   ```bash
   git log --oneline -20
   ```

4. Open an issue in the GitHub repository with the collected diagnostics.
