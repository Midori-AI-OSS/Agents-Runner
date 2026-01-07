#!/usr/bin/env bash
set -euo pipefail

echo "[desktop] starting headless desktop (noVNC)"

export DISPLAY="${DISPLAY:-:1}"
export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-xcb}"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/tmp/xdg-$(id -un)}"
mkdir -p "${XDG_RUNTIME_DIR}"

RUNTIME_BASE="/tmp/agents-runner-desktop/${AGENTS_RUNNER_TASK_ID:-task}"
mkdir -p "${RUNTIME_BASE}"/{run,log,out,config}
mkdir -p "/tmp/agents-artifacts"

echo "[desktop] Synchronizing package database..."
if ! yay -Syu --noconfirm; then
  echo "[desktop] ERROR: Failed to sync package database" >&2
  exit 1
fi

echo "[desktop] Installing official repository packages (one-by-one with retries)..."
OFFICIAL_PKGS=(
  tigervnc
  fluxbox
  xterm
  imagemagick
  xorg-xwininfo
  xcb-util-cursor
  websockify
  wmctrl
  xdotool
  xorg-xprop
  xorg-xauth
  ttf-dejavu
  xorg-fonts-misc
  novnc
)

install_pkg_with_retry() {
  local pkg="$1"
  local max_attempts=3
  local attempt=1
  until yay -S --noconfirm --needed "${pkg}" >/dev/null 2>&1; do
    if [ "${attempt}" -ge "${max_attempts}" ]; then
      echo "[desktop] ERROR: Failed to install ${pkg} after ${max_attempts} attempts" >&2
      return 1
    fi
    echo "[desktop] Retrying install of ${pkg} (attempt $((attempt+1))/${max_attempts})..."
    attempt=$((attempt+1))
    sleep 2
  done
  return 0
}

for pkg in "${OFFICIAL_PKGS[@]}"; do
  if ! install_pkg_with_retry "${pkg}"; then
    echo "[desktop] ERROR: Failed to install required official package: ${pkg}" >&2
    echo "[desktop] Cannot continue without desktop environment" >&2
    exit 1
  fi
done

echo "[desktop] Validating installed components..."
REQUIRED_BINS=(Xvnc fluxbox xterm websockify)
MISSING_BINS=()

for bin in "${REQUIRED_BINS[@]}"; do
  if ! command -v "${bin}" >/dev/null 2>&1; then
    MISSING_BINS+=("${bin}")
  fi
done

if [ ${#MISSING_BINS[@]} -gt 0 ]; then
  echo "[desktop] ERROR: Required binaries not found: ${MISSING_BINS[*]}" >&2
  echo "[desktop] Package installation may have failed silently" >&2
  exit 1
fi

Xvnc "${DISPLAY}" \
  -geometry 1280x800 \
  -depth 24 \
  -SecurityTypes None \
  -localhost \
  -rfbport 5901 \
  >"${RUNTIME_BASE}/log/xvnc.log" 2>&1 &
sleep 0.25

(fluxbox >"${RUNTIME_BASE}/log/fluxbox.log" 2>&1 &) || true
(xterm -geometry 80x24+10+10 >"${RUNTIME_BASE}/log/xterm.log" 2>&1 &) || true

NOVNC_WEB=""
for candidate in "/usr/share/webapps/novnc" "/usr/share/novnc" "/usr/share/noVNC"; do
  if [ -d "${candidate}" ]; then
    NOVNC_WEB="${candidate}"
    break
  fi
done
if [ -z "${NOVNC_WEB}" ]; then
  echo "[desktop] ERROR: noVNC web root not found in expected locations" >&2
  echo "[desktop] Searched: /usr/share/webapps/novnc, /usr/share/novnc, /usr/share/noVNC" >&2
  exit 1
fi

websockify --web="${NOVNC_WEB}" 6080 127.0.0.1:5901 >"${RUNTIME_BASE}/log/novnc.log" 2>&1 &

echo "[desktop] ready"
echo "[desktop] DISPLAY=${DISPLAY}"
echo "[desktop] screenshot: import -display ${DISPLAY} -window root /tmp/agents-artifacts/${AGENTS_RUNNER_TASK_ID:-task}-desktop.png"
