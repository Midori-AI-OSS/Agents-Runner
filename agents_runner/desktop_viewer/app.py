"""Standalone Qt application for displaying noVNC in QWebEngineView.

This runs as a separate process to isolate QtWebEngine crashes from the main UI.
Invocation: python -m agents_runner.desktop_viewer --url <novnc_url> [--title <title>]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox, QVBoxLayout, QWidget

try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
except ImportError:
    QWebEngineView = None


def run_desktop_viewer(args: list[str]) -> int:
    """Run the desktop viewer application.
    
    Args:
        args: Command-line arguments (typically sys.argv)
        
    Returns:
        Exit code (0 for success)
    """
    parser = argparse.ArgumentParser(
        description="Desktop viewer for noVNC (out-of-process)",
        prog="python -m agents_runner.desktop_viewer",
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
    
    if QWebEngineView is None:
        print("Error: QtWebEngine not available", file=sys.stderr)
        return 1
    
    app = QApplication.instance()
    if app is None:
        app = QApplication(args)
    
    # Set application icon if available
    icon_path = Path(__file__).parent.parent / "midoriai-logo.png"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    
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
