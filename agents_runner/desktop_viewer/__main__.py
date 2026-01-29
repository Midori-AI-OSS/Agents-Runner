"""Entry point for running the desktop viewer as a module.

Usage: python -m agents_runner.desktop_viewer --url <novnc_url> [--title <title>]
"""

from __future__ import annotations

import sys

from agents_runner.desktop_viewer.app import run_desktop_viewer

if __name__ == "__main__":
    sys.exit(run_desktop_viewer(sys.argv))
