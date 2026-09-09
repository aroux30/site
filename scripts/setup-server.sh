#!/bin/bash
set -euo pipefail

#######################################################################
# setup-server.sh - Initial server setup script for Ubuntu
#
# Usage: sudo ./scripts/setup-server.sh
#
# This script handles:
#   - Installing Docker and Docker Compose
#   - Creating project directory structure
#   - Setting up firewall (ufw)
#   - Creating .env from template
#   - Pulling and starting services
#   - Running initial database migrations
#
# Requirements:
#   - Ubuntu 22.04 or later
#   - Root or sudo access
#   - Internet connectivity
#######################################################################

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[SETUP $(date '+%H:%M:%S')]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN $(date '+%H:%M:%S')]${NC} $*"; }
error() { echo -e "${RED}[ERROR $(date '+%H:%M:%S')]${NC} $*"; }

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    error "This script must be run as root (use sudo)."
    exit 1
fi

# Configuration
PROJECT_DIR="${PROJECT_DIR:-/opt/app}"
APP_USER="${APP_USER:-deploy}"
REPO_URL="${REPO_URL:-}"

log "Starting server setup..."
log "Project directory: ${PROJECT_DIR}"
log "Application user: ${APP_USER}"

#----------------------------------------------------------------------
# Step 1: System updates
#----------------------------------------------------------------------
log "Updating system packages..."
apt-get update -y
apt-get upgrade -y
apt-get install -y \
    curl \
    wget \
    git \
    ufw \
    fail2ban \
    unzip \
    htop \
    net-tools \
    software-properties-common \
    apt-transport-https \
    ca-certificates \
    gnupg \
    lsb-release

#----------------------------------------------------------------------
# Step 2: Create application user
#----------------------------------------------------------------------
if ! id "$APP_USER" &>/dev/null; then
    log "Creating application user: ${APP_USER}"
    useradd -m -s /bin/bash "$APP_USER"
    usermod -aG sudo "$APP_USER"
else
    log "User ${APP_USER} already exists."
fi

#----------------------------------------------------------------------
# Step 3: Install Docker
#----------------------------------------------------------------------
if ! command -v docker &>/dev/null; then
    log "Installing Docker..."

    # Add Docker GPG key
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
        gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg

    # Add Docker repository
    echo \
        "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
        https://download.docker.com/linux/ubuntu \
        $(lsb_release -cs) stable" | \
        tee /etc/apt/sources.list.d/docker.list > /dev/null

    # Install Docker packages
    apt-get update -y
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

    # Add app user to docker group
    usermod -aG docker "$APP_USER"

    # Enable and start Docker
    systemctl enable docker
    systemctl start docker

    log "Docker installed: $(docker --version)"
else
    log "Docker already installed: $(docker --version)"
fi

# Verify Docker Compose
if docker compose version &>/dev/null; then
    log "Docker Compose available: $(docker compose version)"
else
    error "Docker Compose plugin not found."
    exit 1
fi

#----------------------------------------------------------------------
# Step 4: Setup firewall (ufw)
#----------------------------------------------------------------------
log "Configuring firewall..."

# Reset ufw to defaults
ufw --force reset

# Default policies
ufw default deny incoming
ufw default allow outgoing

# Allow SSH
ufw allow 22/tcp comment "SSH"

# Allow HTTP and HTTPS
ufw allow 80/tcp comment "HTTP"
ufw allow 443/tcp comment "HTTPS"

# Enable firewall
ufw --force enable

log "Firewall configured:"
ufw status verbose

#----------------------------------------------------------------------
# Step 5: Configure fail2ban
#----------------------------------------------------------------------
log "Configuring fail2ban..."
cat > /etc/fail2ban/jail.local <<'EOF'
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 5

[sshd]
enabled = true
port = ssh
filter = sshd
logpath = /var/log/auth.log
maxretry = 3
bantime = 7200
EOF

systemctl enable fail2ban
systemctl restart fail2ban
log "fail2ban configured and started."

#----------------------------------------------------------------------
# Step 6: Create project directory
#----------------------------------------------------------------------
log "Creating project directory structure..."
mkdir -p "${PROJECT_DIR}"
mkdir -p "${PROJECT_DIR}/logs"
mkdir -p "${PROJECT_DIR}/backups"
mkdir -p "${PROJECT_DIR}/data/postgres"
mkdir -p "${PROJECT_DIR}/data/redis"
mkdir -p "${PROJECT_DIR}/nginx/certs"

chown -R "${APP_USER}:${APP_USER}" "${PROJECT_DIR}"

#----------------------------------------------------------------------
# Step 7: Clone repository (if URL provided)
#----------------------------------------------------------------------
if [ -n "$REPO_URL" ]; then
    log "Cloning repository..."
    su - "$APP_USER" -c "git clone ${REPO_URL} ${PROJECT_DIR}/src"
else
    warn "No REPO_URL provided. Skipping repository clone."
    warn "Set REPO_URL environment variable or manually clone your repository."
fi

#----------------------------------------------------------------------
# Step 8: Create .env from template
#----------------------------------------------------------------------
ENV_FILE="${PROJECT_DIR}/.env"
if [ ! -f "$ENV_FILE" ]; then
    log "Creating .env file from template..."
    cat > "$ENV_FILE" <<'EOF'
# Application Settings
APP_ENV=production
APP_DEBUG=false
APP_SECRET_KEY=CHANGE_ME_TO_A_RANDOM_SECRET_KEY
APP_ALLOWED_HOSTS=your-domain.com,www.your-domain.com

# Database Settings
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=app_db
POSTGRES_USER=app_user
POSTGRES_PASSWORD=CHANGE_ME_TO_A_STRONG_PASSWORD

# Redis Settings
REDIS_URL=redis://redis:6379/0

# Email Settings
EMAIL_HOST=smtp.example.com
EMAIL_PORT=587
EMAIL_USER=
EMAIL_PASSWORD=
EMAIL_FROM=noreply@your-domain.com

# SSL / Domain
DOMAIN=your-domain.com
SSL_EMAIL=admin@your-domain.com
EOF

    chown "${APP_USER}:${APP_USER}" "$ENV_FILE"
    chmod 600 "$ENV_FILE"

    warn "============================================"
    warn "IMPORTANT: Edit ${ENV_FILE} and update all"
    warn "placeholder values before starting services!"
    warn "============================================"
else
    log ".env file already exists. Skipping creation."
fi

#----------------------------------------------------------------------
# Step 9: Pull and start services
#----------------------------------------------------------------------
if [ -f "${PROJECT_DIR}/docker-compose.yml" ]; then
    log "Starting Docker services..."
    cd "$PROJECT_DIR"
    su - "$APP_USER" -c "cd ${PROJECT_DIR} && docker compose up -d"
    log "Services started."
else
    warn "No docker-compose.yml found. Skipping service startup."
    warn "Copy your docker-compose.yml to ${PROJECT_DIR} and run:"
    warn "  cd ${PROJECT_DIR} && docker compose up -d"
fi

#----------------------------------------------------------------------
# Step 10: Run initial migrations
#----------------------------------------------------------------------
if [ -f "${PROJECT_DIR}/docker-compose.yml" ]; then
    log "Waiting for database to be ready..."
    sleep 10

    log "Running initial database migrations..."
    su - "$APP_USER" -c "cd ${PROJECT_DIR} && docker compose exec -T backend python manage.py migrate --noinput" || \
        warn "Migration failed. You may need to run migrations manually after services are fully up."
fi

#----------------------------------------------------------------------
# Summary
#----------------------------------------------------------------------
log "============================================"
log "Server setup completed!"
log "============================================"
log ""
log "Next steps:"
log "  1. Edit ${ENV_FILE} with your actual values"
log "  2. Set up SSL certificates (use certbot or similar)"
log "  3. Clone/copy your application code if not done"
log "  4. Run: cd ${PROJECT_DIR} && docker compose up -d"
log "  5. Run migrations: docker compose exec backend python manage.py migrate"
log ""
log "Useful commands:"
log "  docker compose logs -f          # View logs"
log "  docker compose ps               # Check service status"
log "  docker compose restart           # Restart all services"
log "  bash scripts/backup.sh           # Create database backup"
log ""
