#!/usr/bin/env bash
# Immediate, warning-free Windows shutdown.
#
# MSYS_NO_PATHCONV=1 is required: without it Git Bash rewrites "/s" into "S:/"
# and shutdown.exe receives a drive path instead of the /s flag, so the machine
# never powers off.
#
# Usage: shutdown-now.sh [--dry-run]

set -euo pipefail

if [[ "${1:-}" == "--dry-run" ]]; then
  echo "DRY RUN: would run: shutdown.exe /s /t 0 /f"
  exit 0
fi

LOG="C:/Users/Administrator/Desktop/site/.claude/shutdown-now.log"
ts() { date '+%Y-%m-%d %H:%M:%S'; }

echo "$(ts) shutdown-now.sh invoked" >>"$LOG"
MSYS_NO_PATHCONV=1 shutdown.exe /s /t 0 /f >>"$LOG" 2>&1 || true
echo "$(ts) shutdown command dispatched" >>"$LOG"
