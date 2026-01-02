from __future__ import annotations

PIXELARCH_EMERALD_IMAGE = "lunamidori5/pixelarch:emerald"
APP_TITLE = "Midori AI Agents Runner"
PIXELARCH_AGENT_CONTEXT_SUFFIX = (
    "\n\n"
    "Environment context:\n"
    "- You are running inside PixelArch.\n"
    "- You have passwordless sudo.\n"
    "- If you need to install packages, use `yay -Syu`.\n"
    "- You have full control of the container you are running in.\n"
)
