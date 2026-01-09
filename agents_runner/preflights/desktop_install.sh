#!/usr/bin/env bash
set -euo pipefail

echo "[desktop-install] Installing desktop environment packages"

echo "[desktop-install] Synchronizing package database..."
if ! sudo pacman -Syu --noconfirm; then
  echo "[desktop-install] ERROR: Failed to sync package database" >&2
  exit 1
fi

echo "[desktop-install] Installing official repository packages (one-by-one with retries)..."
OFFICIAL_PKGS=(
  tigervnc
  fluxbox
  xterm
  imagemagick
  xorg-xwininfo
  xcb-util-cursor
  wmctrl
  xdotool
  xorg-xprop
  xorg-xauth
  ttf-dejavu
  xorg-fonts-misc
  python-pip
  git
)

install_pkg_with_retry() {
  local pkg="$1"
  local max_attempts=3
  local attempt=1
  until yay -S --noconfirm --needed "${pkg}" >/dev/null 2>&1; do
    if [ "${attempt}" -ge "${max_attempts}" ]; then
      echo "[desktop-install] ERROR: Failed to install ${pkg} after ${max_attempts} attempts" >&2
      return 1
    fi
    echo "[desktop-install] Retrying install of ${pkg} (attempt $((attempt+1))/${max_attempts})..."
    attempt=$((attempt+1))
    sleep 2
  done
  return 0
}

for pkg in "${OFFICIAL_PKGS[@]}"; do
  if ! install_pkg_with_retry "${pkg}"; then
    echo "[desktop-install] ERROR: Failed to install required official package: ${pkg}" >&2
    echo "[desktop-install] Cannot continue without desktop environment" >&2
    exit 1
  fi
done

echo "[desktop-install] Installing websockify via pip..."
if ! pip install websockify --break-system-packages >/dev/null 2>&1; then
  echo "[desktop-install] ERROR: Failed to install websockify via pip" >&2
  exit 1
fi

echo "[desktop-install] Installing noVNC via git clone..."
if [ -d /usr/share/novnc ]; then
  echo "[desktop-install] noVNC already exists at /usr/share/novnc, skipping..."
else
  if ! git clone --depth 1 https://github.com/novnc/noVNC.git /usr/share/novnc >/dev/null 2>&1; then
    echo "[desktop-install] ERROR: Failed to clone noVNC repository" >&2
    exit 1
  fi
fi

echo "[desktop-install] Validating installed components..."
REQUIRED_BINS=(Xvnc fluxbox xterm)
MISSING_BINS=()

for bin in "${REQUIRED_BINS[@]}"; do
  if ! command -v "${bin}" >/dev/null 2>&1; then
    MISSING_BINS+=("${bin}")
  fi
done

if [ ${#MISSING_BINS[@]} -gt 0 ]; then
  echo "[desktop-install] ERROR: Required binaries not found: ${MISSING_BINS[*]}" >&2
  echo "[desktop-install] Package installation may have failed silently" >&2
  exit 1
fi

echo "[desktop-install] Validating websockify installation..."
if ! command -v websockify >/dev/null 2>&1 && ! python -m websockify --version >/dev/null 2>&1; then
  echo "[desktop-install] ERROR: websockify not accessible via command or python module" >&2
  exit 1
fi

echo "[desktop-install] Validating noVNC installation..."
if [ ! -d /usr/share/novnc ] || [ ! -f /usr/share/novnc/vnc.html ]; then
  echo "[desktop-install] ERROR: noVNC not found at /usr/share/novnc or vnc.html missing" >&2
  exit 1
fi

echo "[desktop-install] All packages installed and validated successfully"
