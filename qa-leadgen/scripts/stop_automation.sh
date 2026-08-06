#!/usr/bin/env bash
# Stop QA Lead-Gen automation daemon
set -euo pipefail
cd "$(dirname "$0")/.."
python3 main.py automate stop
