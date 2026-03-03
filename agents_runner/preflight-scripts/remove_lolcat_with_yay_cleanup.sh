#!/usr/bin/env bash
set -euo pipefail

# Demonstrates a PixelArch remove flow with yay.
yay -Syu --noconfirm
if yay -Q lolcat >/dev/null 2>&1; then
  yay -Rns --noconfirm lolcat
else
  echo "[settings-preflight] lolcat is not installed; nothing to remove"
fi
yay -Yccc --noconfirm
