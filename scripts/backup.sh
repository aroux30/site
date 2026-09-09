#!/bin/bash
set -euo pipefail

#######################################################################
# backup.sh - PostgreSQL backup script
#
# Usage: ./scripts/backup.sh [options]
#   -d, --database    Database name (default: from .env POSTGRES_DB)
#   -o, --output      Output directory (default: ./backups)
#   -r, --retention   Days to keep backups (default: 30)
#   -s, --s3-bucket   S3 bucket for remote upload (optional)
#   -h, --help        Show this help message
#
# Creates compressed PostgreSQL backups with timestamped filenames.
# Automatically removes backups older than the retention period.
#######################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[BACKUP $(date '+%H:%M:%S')]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN $(date '+%H:%M:%S')]${NC} $*"; }
error() { echo -e "${RED}[ERROR $(date '+%H:%M:%S')]${NC} $*"; }

# Defaults
BACKUP_DIR="${PROJECT_DIR}/backups"
RETENTION_DAYS=30
S3_BUCKET=""
CONTAINER_NAME="postgres"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"

# Load environment variables
if [ -f "${PROJECT_DIR}/.env" ]; then
    set -a
    source "${PROJECT_DIR}/.env"
    set +a
fi

DB_NAME="${POSTGRES_DB:-app_db}"
DB_USER="${POSTGRES_USER:-app_user}"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -d|--database) DB_NAME="$2"; shift 2 ;;
        -o|--output) BACKUP_DIR="$2"; shift 2 ;;
        -r|--retention) RETENTION_DAYS="$2"; shift 2 ;;
        -s|--s3-bucket) S3_BUCKET="$2"; shift 2 ;;
        -h|--help)
            head -20 "$0" | tail -14
            exit 0
            ;;
        *) error "Unknown option: $1"; exit 1 ;;
    esac
done

# Ensure backup directory exists
mkdir -p "$BACKUP_DIR"

BACKUP_FILE="${BACKUP_DIR}/${DB_NAME}_${TIMESTAMP}.sql.gz"

log "Starting backup of database: ${DB_NAME}"
log "Backup file: ${BACKUP_FILE}"

#----------------------------------------------------------------------
# Step 1: Create backup using pg_dump
#----------------------------------------------------------------------
log "Running pg_dump..."

docker compose -f "${PROJECT_DIR}/docker-compose.yml" exec -T "$CONTAINER_NAME" \
    pg_dump -U "$DB_USER" -d "$DB_NAME" --no-owner --no-acl --clean --if-exists \
    | gzip > "$BACKUP_FILE"

# Verify backup file
if [ ! -s "$BACKUP_FILE" ]; then
    error "Backup file is empty or was not created."
    rm -f "$BACKUP_FILE"
    exit 1
fi

BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
log "Backup created successfully: ${BACKUP_FILE} (${BACKUP_SIZE})"

#----------------------------------------------------------------------
# Step 2: Create checksum
#----------------------------------------------------------------------
sha256sum "$BACKUP_FILE" > "${BACKUP_FILE}.sha256"
log "Checksum saved: ${BACKUP_FILE}.sha256"

#----------------------------------------------------------------------
# Step 3: Upload to S3 (if configured)
#----------------------------------------------------------------------
if [ -n "$S3_BUCKET" ]; then
    if command -v aws &>/dev/null; then
        log "Uploading backup to S3: ${S3_BUCKET}"
        aws s3 cp "$BACKUP_FILE" "s3://${S3_BUCKET}/backups/$(basename "$BACKUP_FILE")"
        aws s3 cp "${BACKUP_FILE}.sha256" "s3://${S3_BUCKET}/backups/$(basename "${BACKUP_FILE}.sha256")"
        log "Backup uploaded to S3 successfully."
    else
        warn "AWS CLI not installed. Skipping S3 upload."
    fi
fi

#----------------------------------------------------------------------
# Step 4: Enforce retention policy
#----------------------------------------------------------------------
log "Applying retention policy: keeping backups from last ${RETENTION_DAYS} days"

DELETED_COUNT=0
while IFS= read -r -d '' old_backup; do
    rm -f "$old_backup"
    rm -f "${old_backup}.sha256"
    DELETED_COUNT=$((DELETED_COUNT + 1))
    log "Deleted old backup: $(basename "$old_backup")"
done < <(find "$BACKUP_DIR" -name "*.sql.gz" -type f -mtime +"$RETENTION_DAYS" -print0)

if [ "$DELETED_COUNT" -gt 0 ]; then
    log "Removed ${DELETED_COUNT} old backup(s)."
else
    log "No old backups to remove."
fi

#----------------------------------------------------------------------
# Summary
#----------------------------------------------------------------------
TOTAL_BACKUPS=$(find "$BACKUP_DIR" -name "*.sql.gz" -type f | wc -l)
TOTAL_SIZE=$(du -sh "$BACKUP_DIR" 2>/dev/null | cut -f1)

log "============================================"
log "Backup completed successfully!"
log "  Database:       ${DB_NAME}"
log "  File:           ${BACKUP_FILE}"
log "  Size:           ${BACKUP_SIZE}"
log "  Total backups:  ${TOTAL_BACKUPS}"
log "  Total size:     ${TOTAL_SIZE}"
log "============================================"
