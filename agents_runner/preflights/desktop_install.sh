#!/usr/bin/env bash
set -euo pipefail

echo "[desktop/setup][INFO] Installing desktop environment packages"

echo "[desktop/setup][INFO] Synchronizing package database..."
if ! yay -Syu --noconfirm; then
  echo "[desktop/setup][ERROR] Failed to sync package database" >&2
  exit 1
fi

echo "[desktop/setup][INFO] Installing official repository packages (one-by-one with retries)..."
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
      echo "[desktop/setup][ERROR] Failed to install ${pkg} after ${max_attempts} attempts" >&2
      return 1
    fi
    echo "[desktop/setup][INFO] Retrying install of ${pkg} (attempt $((attempt+1))/${max_attempts})..."
    attempt=$((attempt+1))
    sleep 2
  done
  return 0
}

for pkg in "${OFFICIAL_PKGS[@]}"; do
  if ! install_pkg_with_retry "${pkg}"; then
    echo "[desktop/setup][ERROR] Failed to install required official package: ${pkg}" >&2
    echo "[desktop/setup][ERROR] Cannot continue without desktop environment" >&2
    exit 1
  fi
done

echo "[desktop/setup][INFO] Validating installed components..."
REQUIRED_BINS=(Xvnc fluxbox xterm websockify)
MISSING_BINS=()

for bin in "${REQUIRED_BINS[@]}"; do
  if ! command -v "${bin}" >/dev/null 2>&1; then
    MISSING_BINS+=("${bin}")
  fi
done

if [ ${#MISSING_BINS[@]} -gt 0 ]; then
  echo "[desktop/setup][ERROR] Required binaries not found: ${MISSING_BINS[*]}" >&2
  echo "[desktop/setup][ERROR] Package installation may have failed silently" >&2
  exit 1
fi

echo "[desktop/setup][INFO] All packages installed and validated successfully"
