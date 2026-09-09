#!/bin/bash
set -euo pipefail

#######################################################################
# restore.sh - Database restore script
#
# Usage: ./scripts/restore.sh [options]
#   -f, --file        Backup file to restore (required)
#   -d, --database    Target database name (default: from .env POSTGRES_DB)
#   -y, --yes         Skip confirmation prompt
#   -h, --help        Show this help message
#
# Restores a PostgreSQL database from a compressed backup file
# created by backup.sh.
#######################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[RESTORE $(date '+%H:%M:%S')]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN $(date '+%H:%M:%S')]${NC} $*"; }
error() { echo -e "${RED}[ERROR $(date '+%H:%M:%S')]${NC} $*"; }

# Defaults
BACKUP_FILE=""
CONTAINER_NAME="postgres"
SKIP_CONFIRM=false

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
        -f|--file) BACKUP_FILE="$2"; shift 2 ;;
        -d|--database) DB_NAME="$2"; shift 2 ;;
        -y|--yes) SKIP_CONFIRM=true; shift ;;
        -h|--help)
            head -16 "$0" | tail -12
            exit 0
            ;;
        *) error "Unknown option: $1"; exit 1 ;;
    esac
done

#----------------------------------------------------------------------
# Validate inputs
#----------------------------------------------------------------------
if [ -z "$BACKUP_FILE" ]; then
    error "Backup file is required. Use -f or --file to specify."
    echo ""
    echo "Available backups:"
    BACKUP_DIR="${PROJECT_DIR}/backups"
    if [ -d "$BACKUP_DIR" ]; then
        ls -lh "$BACKUP_DIR"/*.sql.gz 2>/dev/null || echo "  No backups found in ${BACKUP_DIR}"
    fi
    exit 1
fi

if [ ! -f "$BACKUP_FILE" ]; then
    error "Backup file not found: ${BACKUP_FILE}"
    exit 1
fi

#----------------------------------------------------------------------
# Verify checksum (if available)
#----------------------------------------------------------------------
if [ -f "${BACKUP_FILE}.sha256" ]; then
    log "Verifying backup checksum..."
    if sha256sum -c "${BACKUP_FILE}.sha256" --quiet 2>/dev/null; then
        log "Checksum verification passed."
    else
        error "Checksum verification FAILED. Backup may be corrupted."
        exit 1
    fi
else
    warn "No checksum file found. Skipping integrity check."
fi

#----------------------------------------------------------------------
# Confirmation prompt
#----------------------------------------------------------------------
BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)

echo ""
echo "============================================"
echo "  Database Restore"
echo "============================================"
echo "  Backup file:    ${BACKUP_FILE}"
echo "  File size:      ${BACKUP_SIZE}"
echo "  Target DB:      ${DB_NAME}"
echo "  Target user:    ${DB_USER}"
echo "============================================"
echo ""

if [ "$SKIP_CONFIRM" != true ]; then
    warn "WARNING: This will overwrite the existing database '${DB_NAME}'!"
    read -r -p "Are you sure you want to proceed? (yes/no): " CONFIRM
    if [ "$CONFIRM" != "yes" ]; then
        log "Restore cancelled by user."
        exit 0
    fi
fi

#----------------------------------------------------------------------
# Step 1: Create a safety backup before restoring
#----------------------------------------------------------------------
log "Creating safety backup of current database..."
SAFETY_BACKUP="${PROJECT_DIR}/backups/${DB_NAME}_pre_restore_$(date +%Y%m%d_%H%M%S).sql.gz"

docker compose -f "${PROJECT_DIR}/docker-compose.yml" exec -T "$CONTAINER_NAME" \
    pg_dump -U "$DB_USER" -d "$DB_NAME" --no-owner --no-acl \
    | gzip > "$SAFETY_BACKUP" 2>/dev/null || true

if [ -s "$SAFETY_BACKUP" ]; then
    log "Safety backup created: ${SAFETY_BACKUP}"
else
    warn "Could not create safety backup (database may not exist yet)."
    rm -f "$SAFETY_BACKUP"
fi

#----------------------------------------------------------------------
# Step 2: Stop application services (keep database running)
#----------------------------------------------------------------------
log "Stopping application services..."
docker compose -f "${PROJECT_DIR}/docker-compose.yml" stop backend || true
sleep 2

#----------------------------------------------------------------------
# Step 3: Terminate existing connections
#----------------------------------------------------------------------
log "Terminating existing database connections..."
docker compose -f "${PROJECT_DIR}/docker-compose.yml" exec -T "$CONTAINER_NAME" \
    psql -U "$DB_USER" -d postgres -c \
    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '${DB_NAME}' AND pid <> pg_backend_pid();" \
    2>/dev/null || true

#----------------------------------------------------------------------
# Step 4: Restore the backup
#----------------------------------------------------------------------
log "Restoring database from backup..."

gunzip -c "$BACKUP_FILE" | \
    docker compose -f "${PROJECT_DIR}/docker-compose.yml" exec -T "$CONTAINER_NAME" \
    psql -U "$DB_USER" -d "$DB_NAME" --single-transaction 2>&1 | \
    tail -5

log "Database restored successfully."

#----------------------------------------------------------------------
# Step 5: Restart application services
#----------------------------------------------------------------------
log "Restarting application services..."
docker compose -f "${PROJECT_DIR}/docker-compose.yml" start backend

#----------------------------------------------------------------------
# Step 6: Verify restore
#----------------------------------------------------------------------
log "Verifying restored database..."
sleep 3

TABLE_COUNT=$(docker compose -f "${PROJECT_DIR}/docker-compose.yml" exec -T "$CONTAINER_NAME" \
    psql -U "$DB_USER" -d "$DB_NAME" -t -c \
    "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';" \
    2>/dev/null | tr -d ' ')

log "============================================"
log "Database restore completed successfully!"
log "  Database:     ${DB_NAME}"
log "  Tables found: ${TABLE_COUNT}"
log "  Source:       ${BACKUP_FILE}"
if [ -s "$SAFETY_BACKUP" ]; then
    log "  Safety backup: ${SAFETY_BACKUP}"
fi
log "============================================"
