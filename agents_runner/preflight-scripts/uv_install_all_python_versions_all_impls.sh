#!/usr/bin/env bash
set -euo pipefail

# Demonstrates installing every downloadable uv Python key for this platform.
if ! command -v jq >/dev/null 2>&1; then
  echo "[settings-preflight] jq is required for this preset."
  exit 1
fi

mapfile -t python_keys < <(
  uv python list --only-downloads --all-versions --output-format json | jq -r '.[].key'
)

if [ "${#python_keys[@]}" -eq 0 ]; then
  echo "[settings-preflight] No downloadable Python versions were returned by uv."
  exit 0
fi

for key in "${python_keys[@]}"; do
  echo "[settings-preflight] uv python install ${key}"
  uv python install "${key}"
done
