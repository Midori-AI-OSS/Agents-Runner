#!/usr/bin/env bash
set -euo pipefail

# Source common log functions
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/log_common.sh"

log_info desktop vnc "Starting headless desktop (noVNC)"

# Quick runtime validation - check binaries exist
log_info desktop vnc "Validating required binaries..."
REQUIRED_BINS=(Xvnc fluxbox xterm websockify)
MISSING_BINS=()

for bin in "${REQUIRED_BINS[@]}"; do
  if ! command -v "${bin}" >/dev/null 2>&1; then
    MISSING_BINS+=("${bin}")
  fi
done

if [ ${#MISSING_BINS[@]} -gt 0 ]; then
  log_error desktop vnc "Required binaries not found: ${MISSING_BINS[*]}" >&2
  log_error desktop vnc "Please run desktop_install.sh first" >&2
  exit 1
fi

# Environment variable setup
export DISPLAY="${DISPLAY:-:1}"
export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-xcb}"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/tmp/xdg-$(id -un)}"
mkdir -p "${XDG_RUNTIME_DIR}"

# Create task-specific runtime directories
RUNTIME_BASE="/tmp/agents-runner-desktop/${AGENTS_RUNNER_TASK_ID:-task}"
mkdir -p "${RUNTIME_BASE}"/{run,log,out,config}
mkdir -p "/tmp/agents-artifacts"

# Configurable ports and geometry
VNC_PORT="${VNC_PORT:-5901}"
NOVNC_PORT="${NOVNC_PORT:-6080}"
SCREEN_GEOMETRY="${SCREEN_GEOMETRY:-1280x800}"
SCREEN_DEPTH="${SCREEN_DEPTH:-24}"

# Start Xvnc
log_info desktop vnc "Starting Xvnc on ${DISPLAY}..."
Xvnc "${DISPLAY}" \
  -geometry "${SCREEN_GEOMETRY}" \
  -depth "${SCREEN_DEPTH}" \
  -SecurityTypes None \
  -localhost \
  -rfbport "${VNC_PORT}" \
  >"${RUNTIME_BASE}/log/xvnc.log" 2>&1 &
sleep 0.25

# Start fluxbox window manager
log_info desktop vnc "Starting fluxbox..."
(fluxbox >"${RUNTIME_BASE}/log/fluxbox.log" 2>&1 &) || true

# Start xterm
log_info desktop vnc "Starting xterm..."
(xterm -geometry 80x24+10+10 >"${RUNTIME_BASE}/log/xterm.log" 2>&1 &) || true

# Source noVNC path
if [ ! -f /etc/default/novnc-path ]; then
  log_warn desktop vnc "/etc/default/novnc-path not found, attempting discovery..." >&2
  NOVNC_WEB=""
  for candidate in "/usr/share/webapps/novnc" "/usr/share/novnc" "/usr/share/noVNC"; do
    if [ -d "${candidate}" ]; then
      NOVNC_WEB="${candidate}"
      break
    fi
  done
  if [ -z "${NOVNC_WEB}" ]; then
    log_error desktop vnc "noVNC web root not found in expected locations" >&2
    log_error desktop vnc "Searched: /usr/share/webapps/novnc, /usr/share/novnc, /usr/share/noVNC" >&2
    log_error desktop vnc "Please run desktop_setup.sh first" >&2
    exit 1
  fi
else
  # shellcheck source=/dev/null
  source /etc/default/novnc-path
fi

# Start websockify with noVNC
log_info desktop vnc "Starting websockify on port ${NOVNC_PORT}..."
websockify --web="${NOVNC_WEB}" "${NOVNC_PORT}" "127.0.0.1:${VNC_PORT}" >"${RUNTIME_BASE}/log/novnc.log" 2>&1 &

# Output ready status with noVNC URL
log_info desktop vnc "ready"
log_info desktop vnc "DISPLAY=${DISPLAY}"
log_info desktop vnc "noVNC URL: http://localhost:${NOVNC_PORT}/vnc.html"
log_info desktop vnc "screenshot: import -display ${DISPLAY} -window root /tmp/agents-artifacts/${AGENTS_RUNNER_TASK_ID:-task}-desktop.png"
