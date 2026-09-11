#!/usr/bin/env bash
# Shell execution script for headless Locust stress testing
set -euo pipefail

TARGET_HOST="${TARGET_HOST:-https://site.arouxpingg.com}"
USERS="${USERS:-1000}"
SPAWN_RATE="${SPAWN_RATE:-100}"
RUN_TIME="${RUN_TIME:-1m}"
OUTPUT_DIR="load_tests/reports"

mkdir -p "$OUTPUT_DIR"

echo "============================================================"
echo " Starting Distributed Locust Stress Test"
echo " Target:     $TARGET_HOST"
echo " Users:      $USERS"
echo " Spawn Rate: $SPAWN_RATE users/s"
echo " Duration:   $RUN_TIME"
echo "============================================================"

python load_tests/run_stress_test.py \
  --host "$TARGET_HOST" \
  --users "$USERS" \
  --spawn-rate "$SPAWN_RATE" \
  --run-time "$RUN_TIME" \
  --output-dir "$OUTPUT_DIR" \
  --headless
