from __future__ import annotations

import os
import sys
from pathlib import Path


def _append_chromium_flags(existing: str, extra_flags: list[str]) -> str:
    tokens: list[str] = []
    existing = (existing or "").strip()
    if existing:
        tokens.extend(existing.split())
    existing_set = set(tokens)
    for flag in extra_flags:
        if flag not in existing_set:
            tokens.append(flag)
            existing_set.add(flag)
    return " ".join(tokens).strip()


def _configure_qtwebengine_runtime() -> None:
    fontconfig_file = os.environ.get("FONTCONFIG_FILE")
    if not fontconfig_file:
        candidate = Path("/etc/fonts/fonts.conf")
        if candidate.is_file():
            os.environ["FONTCONFIG_FILE"] = str(candidate)

    if not Path("/dev/dri").exists():
        flags = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "")
        os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = _append_chromium_flags(
            flags,
            [
                "--disable-gpu",
                "--disable-gpu-compositing",
                "--disable-features=Vulkan",
            ],
        )


def _initialize_qtwebengine() -> None:
    """Initialize QtWebEngine at startup to prevent lazy-load flash."""
    try:
        from PySide6.QtWebEngineWidgets import QWebEngineView
        import logging
        logger = logging.getLogger(__name__)
        
        # Create a hidden dummy view to force Chromium initialization
        # This is garbage collected after initialization
        dummy = QWebEngineView()
        dummy.setParent(None)
        dummy.hide()
        dummy.deleteLater()
        
        logger.info("QtWebEngine initialized successfully")
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.debug(f"QtWebEngine not available: {e}")


def run_app(argv: list[str]) -> None:
    # Install crash handler as early as possible
    from agents_runner.diagnostics.crash_handler import install_crash_handler
    install_crash_handler()

    _configure_qtwebengine_runtime()

    from PySide6.QtWidgets import QApplication

    from agents_runner.environments import load_environments
    from agents_runner.setup.orchestrator import check_setup_complete
    from agents_runner.style import app_stylesheet
    from agents_runner.ui.constants import APP_TITLE
    from agents_runner.ui.dialogs.first_run_setup import FirstRunSetupDialog
    from agents_runner.ui.dialogs.new_environment_wizard import NewEnvironmentWizard
    from agents_runner.ui.icons import _app_icon
    from agents_runner.ui.main_window import MainWindow

    app = QApplication(argv)
    app.setApplicationDisplayName(APP_TITLE)
    app.setApplicationName(APP_TITLE)
    icon = _app_icon()
    if icon is not None:
        app.setWindowIcon(icon)
    app.setStyleSheet(app_stylesheet())

    # Initialize QtWebEngine early to prevent lazy-load flash
    _initialize_qtwebengine()

    # Check for crash reports from previous session
    from agents_runner.diagnostics.crash_detection import should_notify_crash
    from agents_runner.diagnostics.crash_detection import mark_crashes_notified
    from agents_runner.diagnostics.paths import crash_reports_dir
    from PySide6.QtWidgets import QMessageBox
    from PySide6.QtGui import QDesktopServices
    from PySide6.QtCore import QUrl
    
    if should_notify_crash():
        msg = QMessageBox()
        msg.setWindowTitle("Crash Detected")
        msg.setText("A crash was detected from a previous session.")
        msg.setInformativeText("A crash report was saved. Would you like to open the crash reports folder?")
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg.setDefaultButton(QMessageBox.No)
        result = msg.exec()
        
        if result == QMessageBox.Yes:
            QDesktopServices.openUrl(QUrl.fromLocalFile(crash_reports_dir()))
        
        mark_crashes_notified()

    # Check if first-run setup is needed
    if not check_setup_complete():
        dialog = FirstRunSetupDialog(parent=None)
        dialog.exec()

    # Check if user has no environments and show wizard
    if not load_environments():
        wizard = NewEnvironmentWizard(parent=None)
        wizard.exec()

    window = MainWindow()
    if icon is not None:
        window.setWindowIcon(icon)
    window.show()
    sys.exit(app.exec())
