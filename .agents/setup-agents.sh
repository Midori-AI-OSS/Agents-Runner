#!/usr/bin/env bash
set -euo pipefail

uv sync
uv sync --group ci
git config --local core.hooksPath .githooks

if [ "${MIDORI_AI_AGENTS_RUNNER_INTERACTIVE:-false}" != "true" ]; then
  echo "Sleeping for a bit to let you stop incase you fucked up Luna" | lolcat
  sleep 45
fi
