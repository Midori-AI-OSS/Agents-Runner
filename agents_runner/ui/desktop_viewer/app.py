"""Standalone Qt application for displaying noVNC in QWebEngineView.

This runs as a separate process to isolate QtWebEngine crashes from the main UI.
Invocation: python -m agents_runner.ui.desktop_viewer --url <novnc_url> [--title <title>]
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)
from midori_ai_logger import MidoriAiLogger

logger = MidoriAiLogger(channel=None, name=__name__)

QWebEngineView = None


def _is_truthy_env(name: str) -> bool:
    value = str(os.environ.get(name, "")).strip().lower()
    return value in {"1", "true", "yes", "on"}


def _debug_log(message: str) -> None:
    if not _is_truthy_env("AGENTS_RUNNER_DESKTOP_VIEWER_DEBUG"):
        return
    logger.rprint(f"[Desktop Viewer] {message}", mode="debug")


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


_DESKTOP_VIEWER_FAULT_LOG_HANDLE = None


def _maybe_enable_desktop_viewer_faulthandler() -> Path | None:
    enabled = _is_truthy_env("AGENTS_RUNNER_FAULTHANDLER") or _is_truthy_env(
        "AGENTS_RUNNER_DESKTOP_VIEWER_FAULTHANDLER"
    )
    if not enabled:
        return None

    try:
        import faulthandler

        log_dir = Path.home() / ".midoriai" / "agents-runner"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "desktop-viewer-faulthandler.log"
        handle = open(log_path, "a", encoding="utf-8")
        faulthandler.enable(file=handle, all_threads=True)

        global _DESKTOP_VIEWER_FAULT_LOG_HANDLE
        _DESKTOP_VIEWER_FAULT_LOG_HANDLE = handle
        return log_path
    except Exception:
        return None


def _configure_webengine_runtime() -> None:
    try:
        from agents_runner.ui.runtime.app import _configure_qtwebengine_runtime

        _configure_qtwebengine_runtime()
    except Exception:
        pass

    flags = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "")
    if _is_truthy_env("AGENTS_RUNNER_DESKTOP_VIEWER_DISABLE_GPU"):
        flags = _append_chromium_flags(
            flags,
            [
                "--disable-gpu",
                "--disable-gpu-compositing",
                "--disable-features=Vulkan",
            ],
        )

    if _is_truthy_env("AGENTS_RUNNER_DESKTOP_VIEWER_DISABLE_VULKAN"):
        flags = _append_chromium_flags(flags, ["--disable-features=Vulkan"])

    if flags.strip():
        os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = flags


def _maybe_install_exception_hooks(argv: list[str]) -> None:
    try:
        from agents_runner.diagnostics.crash_reporting import install_exception_hooks

        install_exception_hooks(argv=list(argv))
    except Exception:
        pass


def run_desktop_viewer(args: list[str]) -> int:
    """Run the desktop viewer application.

    Args:
        args: Command-line arguments (typically sys.argv)

    Returns:
        Exit code (0 for success)
    """
    parser = argparse.ArgumentParser(
        description="Desktop viewer for noVNC (out-of-process)",
        prog="python -m agents_runner.ui.desktop_viewer",
    )
    parser.add_argument(
        "--url",
        required=True,
        help="noVNC URL to display",
    )
    parser.add_argument(
        "--title",
        default="Desktop",
        help="Window title (default: Desktop)",
    )

    parsed = parser.parse_args(args[1:])  # Skip program name

    _configure_webengine_runtime()
    fault_log_path = _maybe_enable_desktop_viewer_faulthandler()
    _maybe_install_exception_hooks(args)
    _debug_log(f"XDG_SESSION_TYPE={os.environ.get('XDG_SESSION_TYPE')}")
    _debug_log(f"QT_QPA_PLATFORM={os.environ.get('QT_QPA_PLATFORM')}")
    _debug_log(
        f"QTWEBENGINE_CHROMIUM_FLAGS={os.environ.get('QTWEBENGINE_CHROMIUM_FLAGS')}"
    )

    try:
        from PySide6.QtWebEngineWidgets import QWebEngineView as _QWebEngineView
    except Exception:
        _QWebEngineView = None

    global QWebEngineView
    QWebEngineView = _QWebEngineView

    if QWebEngineView is None:
        logger.rprint(
            "[Desktop Viewer] QtWebEngine not available; opening URL in system browser",
            mode="warn",
        )
        app = QApplication.instance()
        if app is None:
            app = QApplication(args)
        QDesktopServices.openUrl(QUrl(parsed.url))
        return 0

    app = QApplication.instance()
    if app is None:
        app = QApplication(args)

    # Set application icon if available
    icon_path = Path(__file__).parent.parent / "midoriai-logo.png"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    if fault_log_path is not None:
        logger.rprint(
            f"[Desktop Viewer] faulthandler enabled: {fault_log_path}", mode="normal"
        )

    window = DesktopViewerWindow(url=parsed.url, title=parsed.title)
    window.show()

    return app.exec()


class DesktopViewerWindow(QMainWindow):
    """Main window for the desktop viewer."""

    def __init__(
        self,
        url: str,
        title: str = "Desktop",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.setWindowTitle(title)
        self.resize(1280, 720)

        # Central widget
        central = QWidget()
        self.setCentralWidget(central)

        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # WebEngine view
        if QWebEngineView is None:
            from PySide6.QtWidgets import QLabel

            error_label = QLabel(
                "QtWebEngine not available.\n"
                "Please install PySide6-WebEngine or open the URL in a browser."
            )
            error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(error_label)
            return

        self._web_view = QWebEngineView()
        layout.addWidget(self._web_view)

        # Load the URL
        try:
            self._web_view.setUrl(QUrl(url))
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error loading URL",
                f"Failed to load {url}:\n{e}",
            )


if __name__ == "__main__":
    sys.exit(run_desktop_viewer(sys.argv))
