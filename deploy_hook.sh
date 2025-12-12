#!/bin/bash
set -euo pipefail

# Simple deploy hook: reset working tree to remote and restart services
REPO_DIR="/root/3r3r3r"
LOGFILE="$REPO_DIR/deploy_hook.log"

echo "[$(date -Iseconds)] Deploy hook triggered" >> "$LOGFILE"
cd "$REPO_DIR"
git fetch --all --prune >> "$LOGFILE" 2>&1
git reset --hard origin/main >> "$LOGFILE" 2>&1

# Recreate venv if missing
if [ ! -d "$REPO_DIR/TelegramRevamp/.venv" ]; then
  python3 -m venv "$REPO_DIR/TelegramRevamp/.venv" >> "$LOGFILE" 2>&1 || true
fi

# Install requirements (non-interactive)
source "$REPO_DIR/TelegramRevamp/.venv/bin/activate" || true
if [ -f "$REPO_DIR/TelegramRevamp/requirements.txt" ]; then
  pip install -r "$REPO_DIR/TelegramRevamp/requirements.txt" >> "$LOGFILE" 2>&1 || true
fi

# Restart services (names used in examples)
systemctl restart telegram-bot || true
systemctl restart telegram-webhook || true

echo "[$(date -Iseconds)] Deploy finished" >> "$LOGFILE"
