from __future__ import annotations

import shutil
import subprocess
import sys
import webbrowser

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices


def open_external_url(url: str) -> bool:
    """Open a URL with Qt first, then platform fallbacks."""
    target = str(url or "").strip()
    if not target:
        return False

    try:
        if QDesktopServices.openUrl(QUrl(target)):
            return True
    except Exception:
        pass

    try:
        if webbrowser.open(target):
            return True
    except Exception:
        pass

    opener = ""
    if sys.platform == "darwin":
        opener = shutil.which("open") or ""
    elif sys.platform.startswith("linux"):
        opener = shutil.which("xdg-open") or ""
    if not opener:
        return False

    try:
        subprocess.Popen(
            [opener, target],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except Exception:
        return False
    return True
