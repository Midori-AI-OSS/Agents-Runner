#!/usr/bin/env bash
set -euo pipefail

# Demonstrates a PixelArch uninstall + reinstall flow with yay.
yay -Syu --noconfirm
if yay -Q lolcat >/dev/null 2>&1; then
  yay -Rns --noconfirm lolcat
fi
yay -Syu --noconfirm --needed lolcat
yay -Yccc --noconfirm
