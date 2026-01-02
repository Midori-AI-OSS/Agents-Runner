from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from agents_runner.style import app_stylesheet
from agents_runner.ui.constants import APP_TITLE
from agents_runner.ui.icons import _app_icon
from agents_runner.ui.main_window import MainWindow


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
