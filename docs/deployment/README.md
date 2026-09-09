# Deployment Guide

## Overview

This project uses Docker Compose for container orchestration and GitHub Actions for CI/CD. Deployments are triggered manually via the GitHub Actions workflow dispatch.

## Prerequisites

- Ubuntu 22.04+ server
- Domain name with DNS configured
- GitHub repository with Actions enabled
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
   sudo REPO_URL=https://github.com/your-org/your-repo.git \
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

### Via GitHub Actions (Recommended)

1. Navigate to **Actions** > **Deploy** in GitHub.
2. Click **Run workflow**.
3. Select the target environment (`staging` or `production`).
4. Click **Run workflow** to start.

The workflow will:
- Create a database backup (unless skipped)
- Pull the latest code
- Build and restart containers
- Run migrations
- Perform health checks
- Roll back automatically on failure

### Manual Deployment

```bash
cd /opt/app
bash scripts/deploy.sh production
```

## Required GitHub Secrets

Configure these in **Settings** > **Secrets and variables** > **Actions**:

| Secret                  | Description                          |
|-------------------------|--------------------------------------|
| `SSH_PRIVATE_KEY`       | SSH private key for server access    |
| `PROD_SERVER_HOST`      | Production server IP/hostname        |
| `PROD_SERVER_USER`      | SSH user on production server        |
| `PROD_DEPLOY_PATH`      | Project path on production server    |
| `PROD_HEALTH_URL`       | Production health check endpoint     |
| `STAGING_SERVER_HOST`   | Staging server IP/hostname           |
| `STAGING_SERVER_USER`   | SSH user on staging server           |
| `STAGING_DEPLOY_PATH`   | Project path on staging server       |
| `STAGING_HEALTH_URL`    | Staging health check endpoint        |

## Backup and Restore

### Creating a Backup

```bash
bash scripts/backup.sh
```

Options:
- `-d` / `--database` - database name
- `-o` / `--output` - output directory
- `-r` / `--retention` - days to retain (default: 30)
- `-s` / `--s3-bucket` - S3 bucket for remote upload

### Restoring from Backup

```bash
bash scripts/restore.sh -f backups/app_db_20260909_120000.sql.gz
```

Options:
- `-f` / `--file` - backup file path (required)
- `-d` / `--database` - target database name
- `-y` / `--yes` - skip confirmation prompt

## Rollback Procedure

### Automatic Rollback

The deployment script automatically rolls back if the health check fails after deployment.

### Manual Rollback

```bash
cd /opt/app

# Check recent commits
git log --oneline -10

# Checkout the previous working commit
git checkout <commit-hash>

# Rebuild and restart
docker compose up -d --build
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
