#!/usr/bin/env bash
# Scheduled maintenance cron for the production server (TASK P12-03).
# Install on the host (as root):  bash scripts/install_backup_cron.sh
# Idempotent: safe to re-run; replaces previously installed entries.
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CRON_FILE=/etc/cron.d/ecommerce-maintenance

if [ ! -f "$PROJECT_DIR/scripts/backup.sh" ]; then
  echo "FATAL: scripts/backup.sh not found next to this script." >&2
  exit 1
fi

# Daily 03:30 Tehran-time backup (host clock must be Asia/Tehran; CI deploys
# already assume that timezone), S3 offsite upload when BACKUP_S3_* is set,
# weekly Sunday 04:00 MinIO mirror to the same bucket.
cat > "$CRON_FILE" <<EOF
# Installed by scripts/install_backup_cron.sh — ecommerce platform maintenance
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

# Nightly database backup (pg_dump + gzip + sha256 + optional S3 upload)
30 3 * * * root cd $PROJECT_DIR && bash scripts/backup.sh >> logs/backup.log 2>&1

# Weekly MinIO object-storage mirror (mc mirror --overwrite; keeps off-box copy)
0 4 * * 0 root cd $PROJECT_DIR && bash scripts/minio_mirror.sh >> logs/minio_mirror.log 2>&1
EOF

chmod 644 "$CRON_FILE"
mkdir -p "$PROJECT_DIR/logs"

echo "Installed $CRON_FILE:"
cat "$CRON_FILE"
echo
echo "Cron is active. Verify with: systemctl status cron && grep ecommerce /etc/crontab /etc/cron.d/*"
echo "Restore procedure: docs/deployment/README.md (scripts/restore.sh)"
