#!/usr/bin/env bash
set -euo pipefail

timestamp() {
  date "+%Y-%m-%d %H:%M:%S"
}

log() {
  echo "[$(timestamp)] $*"
}

run_cmd() {
  log "\$ $*"
  "$@"
}

log "[docker] Cleanup started"

log "[docker] Pruning containers…"
run_cmd docker container prune -f

log "[docker] Pruning images…"
run_cmd docker image prune -a -f

log "[docker] Pruning volumes…"
run_cmd docker volume prune -f

log "[docker] Pruning networks…"
run_cmd docker network prune -f

log "[docker] Final system prune…"
run_cmd docker system prune -f -a

log "[docker] Cleanup completed"
