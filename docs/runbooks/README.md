# Operational Runbooks

## Overview

This document contains step-by-step procedures for common operational tasks. Each runbook is designed to be followed by any team member with server access.

---

## Runbook: Scheduled Deployment

**When:** Deploying a new release to production.

### Steps

1. Verify CI pipeline passes on the target commit:
   ```
   GitHub > Actions > CI Pipeline > Verify latest run is green
   ```

2. Create a database backup:
   ```bash
   cd /opt/app
   bash scripts/backup.sh
   ```

3. Trigger the deployment:
   ```
   GitHub > Actions > Deploy > Run workflow > Select "production"
   ```

4. Monitor deployment progress in the GitHub Actions log.

5. Verify the application is healthy:
   ```bash
   curl -s https://your-domain.com/api/health/ | jq .
   docker compose ps
   ```

6. Monitor application logs for errors (first 15 minutes):
   ```bash
   docker compose logs -f --tail=50 backend
   ```

---

## Runbook: Emergency Rollback

**When:** A deployment caused issues that need immediate reversal.

### Steps

1. SSH into the production server:
   ```bash
   ssh deploy@your-server
   ```

2. Identify the previous working commit:
   ```bash
   cd /opt/app
   git log --oneline -5
   ```

3. Roll back to the previous commit:
   ```bash
   git checkout <previous-commit-hash>
   docker compose up -d --build
   ```

4. Verify services are running:
   ```bash
   docker compose ps
   curl -s https://site.arouxpingg.com/readyz
   ```

5. If database migrations need reversal:
   ```bash
   docker compose exec backend alembic downgrade <previous_revision_id>
   ```

6. Notify the team about the rollback and the reason.

---

## Runbook: Database Backup and Restore

**When:** Performing scheduled backups or restoring from a backup.

### Backup

```bash
cd /opt/app

# Standard backup
bash scripts/backup.sh

# Backup with S3 upload
bash scripts/backup.sh -s your-s3-bucket-name

# Backup specific database
bash scripts/backup.sh -d my_database
```

### Restore

```bash
cd /opt/app

# List available backups
ls -lh backups/

# Restore from a specific backup
bash scripts/restore.sh -f backups/app_db_20260909_120000.sql.gz

# Restore without confirmation prompt
bash scripts/restore.sh -f backups/app_db_20260909_120000.sql.gz -y
```

---

## Runbook: SSL Certificate Renewal

**When:** SSL certificates are expiring (Let's Encrypt certificates expire every 90 days).

### Automatic Renewal

Certbot should be configured for automatic renewal:
```bash
sudo systemctl status certbot.timer
```

### Manual Renewal

```bash
# Stop nginx to free port 80
docker compose stop nginx

# Renew certificate
sudo certbot renew

# Restart nginx
docker compose start nginx
```

### Verify Certificate

```bash
echo | openssl s_client -connect your-domain.com:443 -servername your-domain.com 2>/dev/null | openssl x509 -noout -dates
```

---

## Runbook: Scale Services

**When:** Increasing or decreasing the number of worker instances.

### Scale Backend Workers

```bash
cd /opt/app

# Scale to 3 worker instances
docker compose up -d --scale worker=3

# Verify scaling
docker compose ps
```

### Monitor Resource Usage

```bash
# Real-time container stats
docker stats

# Check disk space
df -h

# Check memory
free -h
```

---

## Runbook: Database Maintenance

**When:** Performing periodic database maintenance.

### Vacuum and Analyze

```bash
docker compose exec postgres psql -U app_user -d app_db -c "VACUUM ANALYZE;"
```

### Check Database Size

```bash
docker compose exec postgres psql -U app_user -d app_db -c "
  SELECT pg_size_pretty(pg_database_size('app_db')) AS db_size;
"
```

### Check Table Sizes

```bash
docker compose exec postgres psql -U app_user -d app_db -c "
  SELECT
    schemaname || '.' || tablename AS table,
    pg_size_pretty(pg_total_relation_size(schemaname || '.' || tablename)) AS total_size
  FROM pg_tables
  WHERE schemaname = 'public'
  ORDER BY pg_total_relation_size(schemaname || '.' || tablename) DESC
  LIMIT 20;
"
```

### Check Active Connections

```bash
docker compose exec postgres psql -U app_user -d app_db -c "
  SELECT count(*) AS total,
         state,
         wait_event_type
  FROM pg_stat_activity
  WHERE datname = 'app_db'
  GROUP BY state, wait_event_type;
"
```

---

## Runbook: Log Investigation

**When:** Investigating errors or unexpected behavior.

### Application Logs

```bash
# Last 200 lines of backend logs
docker compose logs --tail=200 backend

# Follow logs in real-time with timestamps
docker compose logs -f -t backend

# Search for errors
docker compose logs backend 2>&1 | grep -i error | tail -20

# Logs from a specific time range
docker compose logs --since="2026-09-09T10:00:00" --until="2026-09-09T12:00:00" backend
```

### System Logs

```bash
# Auth failures
sudo grep "Failed password" /var/log/auth.log | tail -20

# Disk I/O issues
dmesg | grep -i "i/o error"
```

---

## Runbook: Server Reboot

**When:** Server needs to be rebooted for system updates or maintenance.

### Steps

1. Notify the team about planned downtime.

2. Create a database backup:
   ```bash
   cd /opt/app && bash scripts/backup.sh
   ```

3. Gracefully stop all containers:
   ```bash
   docker compose down
   ```

4. Perform the reboot:
   ```bash
   sudo reboot
   ```

5. After reboot, verify Docker is running:
   ```bash
   sudo systemctl status docker
   ```

6. Start all services:
   ```bash
   cd /opt/app && docker compose up -d
   ```

7. Verify all services are healthy:
   ```bash
   docker compose ps
   curl -s http://localhost:8000/api/health/
   ```

---

## Runbook: Add New Team Member Server Access

**When:** Granting a new team member SSH access to the server.

### Steps

1. Get the team member's public SSH key.

2. Add the key to the deploy user's authorized_keys:
   ```bash
   sudo su - deploy
   echo "ssh-ed25519 AAAA... user@email.com" >> ~/.ssh/authorized_keys
   ```

3. Verify the key was added:
   ```bash
   cat ~/.ssh/authorized_keys
   ```

4. Have the team member test their access:
   ```bash
   ssh deploy@your-server
   ```
