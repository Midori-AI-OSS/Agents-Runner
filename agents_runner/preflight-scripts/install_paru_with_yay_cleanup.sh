#!/usr/bin/env bash
set -euo pipefail

# Demonstrates a PixelArch install flow with yay.
yay -Syu --noconfirm --needed paru && yay -Yccc --noconfirm
