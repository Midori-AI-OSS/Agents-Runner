from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from codex_local_conatinerd.style import app_stylesheet
from codex_local_conatinerd.ui.constants import APP_TITLE
from codex_local_conatinerd.ui.icons import _app_icon
from codex_local_conatinerd.ui.main_window import MainWindow


def run_app(argv: list[str]) -> None:
    app = QApplication(argv)
    app.setApplicationDisplayName(APP_TITLE)
    app.setApplicationName(APP_TITLE)
    icon = _app_icon()
    if icon is not None:
        app.setWindowIcon(icon)
    app.setStyleSheet(app_stylesheet())

    window = MainWindow()
    if icon is not None:
        window.setWindowIcon(icon)
    window.show()
    sys.exit(app.exec())
