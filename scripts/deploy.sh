#!/bin/bash
set -euo pipefail

#######################################################################
# deploy.sh - Server deployment script
#
# Usage: ./scripts/deploy.sh [environment]
#   environment: staging | production (default: production)
#
# This script handles:
#   - Pulling latest code
#   - Building Docker images
#   - Running database migrations
#   - Restarting services with zero-downtime
#   - Health check verification
#   - Automatic rollback on failure
#######################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
ENVIRONMENT="${1:-production}"
COMPOSE_FILE="docker-compose.yml"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
LOG_FILE="${PROJECT_DIR}/logs/deploy_${TIMESTAMP}.log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log() {
    echo -e "${GREEN}[DEPLOY $(date '+%H:%M:%S')]${NC} $*" | tee -a "$LOG_FILE"
}

warn() {
    echo -e "${YELLOW}[WARN $(date '+%H:%M:%S')]${NC} $*" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[ERROR $(date '+%H:%M:%S')]${NC} $*" | tee -a "$LOG_FILE"
}

cleanup() {
    if [ $? -ne 0 ]; then
        error "Deployment failed. Check logs at: $LOG_FILE"
    fi
}
trap cleanup EXIT

# Validate environment
if [[ "$ENVIRONMENT" != "staging" && "$ENVIRONMENT" != "production" ]]; then
    error "Invalid environment: $ENVIRONMENT. Use 'staging' or 'production'."
    exit 1
fi

# Use environment-specific compose override if it exists
if [ -f "${PROJECT_DIR}/docker-compose.${ENVIRONMENT}.yml" ]; then
    COMPOSE_FILE="docker-compose.yml -f docker-compose.${ENVIRONMENT}.yml"
fi

# Ensure log directory exists
mkdir -p "${PROJECT_DIR}/logs"

log "Starting deployment to ${ENVIRONMENT}"
log "Project directory: ${PROJECT_DIR}"
log "Compose file(s): ${COMPOSE_FILE}"

cd "$PROJECT_DIR"

# Store current commit for rollback
PREVIOUS_COMMIT="$(git rev-parse HEAD)"
log "Current commit: ${PREVIOUS_COMMIT}"

#----------------------------------------------------------------------
# Step 1: Pull latest code
#----------------------------------------------------------------------
log "Pulling latest code..."
git pull origin "$(git rev-parse --abbrev-ref HEAD)"
CURRENT_COMMIT="$(git rev-parse HEAD)"
log "Updated to commit: ${CURRENT_COMMIT}"

if [ "$PREVIOUS_COMMIT" = "$CURRENT_COMMIT" ]; then
    warn "No new commits. Proceeding with rebuild anyway."
fi

#----------------------------------------------------------------------
# Step 2: Build Docker images
#----------------------------------------------------------------------
log "Building Docker images..."
docker compose -f $COMPOSE_FILE build --no-cache

#----------------------------------------------------------------------
# Step 3: Run database migrations
#----------------------------------------------------------------------
log "Running database migrations with Alembic..."
docker compose -f $COMPOSE_FILE run --rm backend alembic upgrade head

#----------------------------------------------------------------------
# Step 4: Restart services
#----------------------------------------------------------------------
log "Restarting services..."
docker compose -f $COMPOSE_FILE up -d --remove-orphans

#----------------------------------------------------------------------
# Step 5: Clean up old images
#----------------------------------------------------------------------
log "Cleaning up old Docker images..."
docker image prune -f || true

#----------------------------------------------------------------------
# Step 6: Health check
#----------------------------------------------------------------------
log "Running health checks..."
MAX_RETRIES=15
RETRY_INTERVAL=4

for i in $(seq 1 $MAX_RETRIES); do
    # Check backend container directly via internal health probe
    if docker compose -f $COMPOSE_FILE exec -T backend curl -sf http://localhost:8000/readyz > /dev/null 2>&1; then
        log "Health check passed on attempt $i (/readyz responded OK)"
        break
    fi
    if [ "$i" = "$MAX_RETRIES" ]; then
        error "Health check failed after $MAX_RETRIES attempts"
        error "Initiating rollback..."

        # Rollback
        log "Rolling back to commit: ${PREVIOUS_COMMIT}"
        git checkout "$PREVIOUS_COMMIT"
        docker compose -f $COMPOSE_FILE build --no-cache
        docker compose -f $COMPOSE_FILE up -d --remove-orphans

        error "Rollback completed. Services restored to previous version."
        exit 1
    fi
    warn "Health check attempt $i/$MAX_RETRIES failed - retrying in ${RETRY_INTERVAL}s..."
    sleep $RETRY_INTERVAL
done

#----------------------------------------------------------------------
# Step 7: Report status
#----------------------------------------------------------------------
log "============================================"
log "Deployment to ${ENVIRONMENT} completed successfully!"
log "Commit: ${CURRENT_COMMIT}"
log "Time: $(date)"
log "============================================"
