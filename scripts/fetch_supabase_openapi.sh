#!/usr/bin/env bash
set -euo pipefail

# Fetch Supabase OpenAPI (PostgREST) spec and save locally
# Requires SUPABASE_URL and SUPABASE_KEY in environment or .env at repo root.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ -f "$ROOT_DIR/.env" ]; then
  # shellcheck source=/dev/null
  source "$ROOT_DIR/.env"
fi

if [ -z "${SUPABASE_URL:-}" ] || [ -z "${SUPABASE_KEY:-}" ]; then
  echo "ERROR: SUPABASE_URL and SUPABASE_KEY must be set (in .env or environment)" >&2
  exit 1
fi

OUT_DIR="$ROOT_DIR/docs/schema"
mkdir -p "$OUT_DIR"

echo "Fetching OpenAPI spec from $SUPABASE_URL/rest/v1 ..."
curl -s \
  -H "apikey: $SUPABASE_KEY" \
  -H "Authorization: Bearer $SUPABASE_KEY" \
  -H "Accept: application/openapi+json" \
  "$SUPABASE_URL/rest/v1/" \
  | jq . > "$OUT_DIR/supabase_openapi.json"

echo "Saved: $OUT_DIR/supabase_openapi.json"

# Create a compact table->columns summary for quick reference
jq '(.definitions // {}) as $d |
    reduce ($d | keys[]) as $k ({ }; 
      .[$k] = [($d[$k].properties // {}) | keys[]])' \
  "$OUT_DIR/supabase_openapi.json" > "$OUT_DIR/table_columns.json"

echo "Saved: $OUT_DIR/table_columns.json"
