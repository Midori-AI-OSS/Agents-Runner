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

if command -v yay >/dev/null 2>&1; then
  echo "[desktop] Installing official repository packages..."
  if ! yay -S --noconfirm --needed \
    tigervnc \
    fluxbox \
    xterm \
    imagemagick \
    xorg-xwininfo \
    xcb-util-cursor \
    websockify \
    wmctrl \
    xdotool \
    xorg-xprop \
    xorg-xauth \
    ttf-dejavu \
    xorg-fonts-misc; then
    echo "[desktop] WARNING: Some official packages failed to install"
    echo "[desktop] Attempting to continue with available packages..."
  fi
  
  echo "[desktop] Installing AUR packages..."
  if ! yay -S --noconfirm --needed novnc; then
    echo "[desktop] WARNING: novnc (AUR) failed to install"
    echo "[desktop] Desktop web interface may not be available"
  fi
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
  echo "[desktop] ERROR: noVNC web root not found" >&2
  exit 1
fi

websockify --web="${NOVNC_WEB}" 6080 127.0.0.1:5901 >"${RUNTIME_BASE}/log/novnc.log" 2>&1 &

echo "[desktop] ready"
echo "[desktop] DISPLAY=${DISPLAY}"
echo "[desktop] screenshot: import -display ${DISPLAY} -window root /tmp/agents-artifacts/${AGENTS_RUNNER_TASK_ID:-task}-desktop.png"
