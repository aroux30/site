#!/usr/bin/env bash
# Weekly MinIO object-storage mirror to an off-box S3 target (TASK P12-03).
# Requires an mc alias named "offsite" configured once:
#   mc alias set offsite https://<s3-endpoint> <ACCESS_KEY> <SECRET_KEY>
# Optional env: MINIO_BUCKET (default ecommerce), OFFSITE_BUCKET (default ecommerce-mirror)
set -euo pipefail

MINIO_BUCKET="${MINIO_BUCKET:-ecommerce}"
OFFSITE_BUCKET="${OFFSITE_BUCKET:-ecommerce-mirror}"

if ! command -v mc >/dev/null 2>&1; then
  echo "FATAL: mc (MinIO client) not installed on the host." >&2
  echo "Install: curl -o /usr/local/bin/mc https://dl.min.io/client/mc/release/linux-amd64/mc && chmod +x /usr/local/bin/mc" >&2
  exit 1
fi

if ! mc alias list 2>/dev/null | grep -q "offsite"; then
  echo "FATAL: mc alias 'offsite' is not configured." >&2
  echo "Configure once: mc alias set offsite https://<s3-endpoint> <ACCESS_KEY> <SECRET_KEY>" >&2
  exit 1
fi

echo "Mirroring local MinIO bucket '${MINIO_BUCKET}' -> offsite/${OFFSITE_BUCKET}"
mc mirror --overwrite --remove "local/${MINIO_BUCKET}" "offsite/${OFFSITE_BUCKET}"

echo "Mirror complete: $(mc ls "offsite/${OFFSITE_BUCKET}" | wc -l) objects at the destination."
