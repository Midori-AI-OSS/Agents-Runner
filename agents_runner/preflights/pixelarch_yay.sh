#!/usr/bin/env bash
set -u

# Source common log functions
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/log_common.sh"

log_info preflight yay "running: yay -Syu --noconfirm && yay -Yccc --noconfirm"

set +e

yay -Syu --noconfirm
STATUS=$?
if [ $STATUS -ne 0 ]; then
  log_warn preflight yay "yay -Syu failed (exit $STATUS); continuing"
  exit 0
fi

yay -Yccc --noconfirm
STATUS=$?
if [ $STATUS -ne 0 ]; then
  log_warn preflight yay "yay -Yccc failed (exit $STATUS); continuing"
fi

exit 0
