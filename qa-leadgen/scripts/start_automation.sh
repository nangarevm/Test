#!/usr/bin/env bash
# Start QA Lead-Gen automation daemon (Telegram bot + 12h scanning)
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -f config.yaml ]; then
  cp config.example.yaml config.yaml
  echo "Created config.yaml — add your Telegram credentials before running."
fi

python3 main.py automate start "$@"
