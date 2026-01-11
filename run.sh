#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
source .venv/bin/activate

# load .env into shell env (safe for simple KEY=VALUE lines)
if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
fi

PYTHONPATH=src python -m littlelife.app
