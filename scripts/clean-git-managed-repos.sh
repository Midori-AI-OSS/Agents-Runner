#!/usr/bin/env bash
set -euo pipefail

timestamp() {
  date "+%Y-%m-%d %H:%M:%S"
}

log() {
  echo "[$(timestamp)] $*"
}

die() {
  log "ERROR: $*"
  exit 1
}

if [[ $# -lt 1 ]]; then
  die "Usage: $0 <managed-repos-dir>"
fi

TARGET="${1}"
if [[ -z "${TARGET}" ]]; then
  die "Target path is empty"
fi

log "[git] Cleanup started"
log "[git] Target: ${TARGET}"

TARGET_REAL="$(python -c 'import os,sys; print(os.path.realpath(sys.argv[1]))' "${TARGET}" 2>/dev/null || true)"
if [[ -z "${TARGET_REAL}" ]]; then
  TARGET_REAL="${TARGET}"
fi
log "[git] Target (realpath): ${TARGET_REAL}"

if [[ "${TARGET_REAL}" == "/" ]]; then
  die "Refusing to delete /"
fi

case "${TARGET_REAL}" in
  *"/managed-repos"|*"/managed-repos/"*)
    ;;
  *)
    die "Refusing to delete unexpected path (does not look like managed-repos): ${TARGET_REAL}"
    ;;
esac

if [[ ! -e "${TARGET}" ]]; then
  log "[git] Nothing to clean."
  exit 0
fi

log "[git] Removing managed repos directory…"
log "\$ rm -rf ${TARGET}"
rm -rf "${TARGET}"

log "[git] Cleanup completed"
