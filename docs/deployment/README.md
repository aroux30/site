# Deployment Guide

## Overview

This project uses Docker Compose for container orchestration. There is currently **no CI/CD pipeline configured** (this repository has no `.github/` directory and no workflow files) — deployments are performed manually over SSH on the production host, as described below.

## Prerequisites

- Ubuntu 22.04+ server
- Domain name with DNS configured
- The source checked out on the server (a git remote or a copy of the tree)
- SSH key pair for deployment

## Architecture

```
                    ┌─────────────┐
                    │   Nginx     │
                    │  (Reverse   │
                    │   Proxy)    │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
        ┌─────▼─────┐ ┌───▼───┐ ┌─────▼─────┐
        │  Frontend  │ │  API  │ │  Worker   │
        │  (Node.js) │ │(Python│ │ (Celery)  │
        └────────────┘ └───┬───┘ └─────┬─────┘
                           │           │
                    ┌──────▼──────┐    │
                    │  PostgreSQL │◄───┘
                    └─────────────┘
                    ┌─────────────┐
                    │    Redis    │
                    └─────────────┘
```

## Initial Server Setup

1. **Provision a server** (Ubuntu 22.04+ recommended).

2. **Run the setup script:**
   ```bash
   sudo REPO_URL=https://git.example.com/your-org/your-repo.git \
     PROJECT_DIR=/opt/app \
     APP_USER=deploy \
     bash scripts/setup-server.sh
   ```

3. **Configure environment variables:**
   ```bash
   sudo nano /opt/app/.env
   ```
   Update all placeholder values, especially:
   - `APP_SECRET_KEY` - generate a strong random key
   - `POSTGRES_PASSWORD` - use a strong password
   - `DOMAIN` - your actual domain name

4. **Set up SSL certificates:**
   ```bash
   sudo apt install certbot
   sudo certbot certonly --standalone -d your-domain.com
   ```

5. **Start services:**
   ```bash
   cd /opt/app && docker compose up -d
   ```

## Deploying Updates

There is no CI pipeline in this repository, so there is no automated deploy
workflow and no `scripts/deploy.sh`. Deployments are performed by hand over SSH.
**Take a backup first** (see below) — there is no automatic rollback.

### Manual Deployment

```bash
cd /opt/app

# 1. Take a backup before touching anything.
bash scripts/backup.sh

# 2. Update the code (git pull, or rsync/scp the new tree onto the server).
git pull

# 3. Rebuild and restart.
docker compose up -d --build

# 4. Run migrations.
docker compose exec backend alembic upgrade head

# 5. Verify health.
curl -s http://localhost:8000/api/health/
docker compose ps
```

If a deployment fails, roll back with the **Manual Rollback** procedure below.

## Backup and Restore

Backups capture PostgreSQL (source of truth), the MinIO media bucket, and an
Elasticsearch snapshot (derived, skippable). Full detail — retention,
encryption, RPO/RTO and the restore-verification record — lives in
[`docs/runbooks/BACKUP_RESTORE.md`](../runbooks/BACKUP_RESTORE.md).

### Creating a Backup

```bash
bash scripts/backup.sh
```

Options:
- `-d` / `--database` - database name (default: `ecommerce`)
- `-s` / `--bucket` - MinIO bucket to mirror (default: `ecommerce-media`)
- `-o` / `--output` - output directory (default: `backups/`)
- `-r` / `--retain` - keep the last N backups (default: 7), older ones pruned
- `--encrypt` - require AES-256 encryption (fails if `BACKUP_ENCRYPTION_KEY` is unset)
- `--no-minio` / `--no-es` - skip the MinIO / Elasticsearch portions

Output: `backups/app_db_<YYYYmmdd_HHMMSS>.sql.gz` plus a `.sha256` sidecar and a
per-run `manifest_*.txt`. Requires Docker on the host (drives `docker compose exec`).

### Restoring from Backup

```bash
bash scripts/restore.sh -f backups/app_db_20260909_120000.sql.gz
```

Options:
- `-f` / `--file` - backup artifact (required)
- `-d` / `--database` - target database name (default: `ecommerce`)
- `-y` / `--yes` - skip confirmation prompt
- `--force` - overwrite a database that already contains data (otherwise refused)
- `--verify` - restore into a throwaway DB, count rows, then drop it (non-destructive)

The checksum is always verified before restoring. Encrypted (`.enc`) artifacts
are decrypted transparently.

### Verifying a Restore (do this regularly)

A backup that has never been restored is not proof. The verify path restores
into a throwaway database, prints key-table row counts, and drops it:

```bash
bash scripts/verify_backup.sh            # newest backup in backups/
bash scripts/verify_backup.sh -f backups/app_db_20260909_120000.sql.gz
```

### Scheduling

Nightly backups and a weekly verification are provided as a cron fragment
(`scripts/cron.d/ecommerce-backup`) and as systemd units
(`scripts/systemd/`). Installation is documented in the backup runbook.

## Rollback Procedure

### Manual Rollback

There is no automated rollback (no CI pipeline). Roll back by hand.

```bash
cd /opt/app

# Check recent commits
git log --oneline -10

# Checkout the previous working commit
git checkout <commit-hash>

# Rebuild and restart
docker compose up -d --build

# If the rollback requires reverting data, restore the pre-deploy backup
# (this OVERWRITES the database — confirm the artifact first with --verify):
bash scripts/verify_backup.sh
bash scripts/restore.sh -f backups/app_db_<timestamp>.sql.gz
```

## Monitoring

### View Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f backend
docker compose logs -f postgres

# Last 100 lines
docker compose logs --tail=100 backend
```

### Check Service Status

```bash
docker compose ps
docker stats
```

## Environment-Specific Configuration

Use Docker Compose override files for environment-specific settings:

- `docker-compose.yml` - base configuration
- `docker-compose.staging.yml` - staging overrides
- `docker-compose.production.yml` - production overrides
