#!/usr/bin/env bash
# Toggle PLC mode in .env between simulation and real
set -euo pipefail

ENV_FILE="${1:-.env}"
MODE="${2:-}"

usage() {
  echo "Usage: $0 [path/to/.env] <simulation|real>" >&2
  exit 1
}

if [[ -z "$MODE" ]]; then
  usage
fi

if [[ "$MODE" != "simulation" && "$MODE" != "real" ]]; then
  usage
fi

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Creating $ENV_FILE..."
  touch "$ENV_FILE"
fi

if grep -q '^PLC_TYPE=' "$ENV_FILE"; then
  sed -i.bak "s/^PLC_TYPE=.*/PLC_TYPE=$MODE/" "$ENV_FILE"
else
  echo "PLC_TYPE=$MODE" >> "$ENV_FILE"
fi

echo "Updated $ENV_FILE: PLC_TYPE=$MODE"

