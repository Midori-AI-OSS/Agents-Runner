"""Diagnostics bundle creation dialog."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtCore import QThread
from PySide6.QtCore import Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QDialog
from PySide6.QtWidgets import QHBoxLayout
from PySide6.QtWidgets import QLabel
from PySide6.QtWidgets import QMessageBox
from PySide6.QtWidgets import QPushButton
from PySide6.QtWidgets import QVBoxLayout
from PySide6.QtWidgets import QWidget

from agents_runner.diagnostics.bundle_builder import create_diagnostics_bundle
from agents_runner.diagnostics.paths import bundles_dir
from agents_runner.style.palette import TEXT_PRIMARY
from agents_runner.style.palette import TEXT_PLACEHOLDER
from agents_runner.widgets import GlassCard


class BundleCreationWorker(QThread):
    """Worker thread for creating diagnostics bundle."""
    
    finished = Signal(str, str)  # bundle_path, error
    
    def __init__(self, settings_data: dict[str, object] | None = None):
        super().__init__()
        self._settings_data = settings_data
    
    def run(self) -> None:
        """Create diagnostics bundle in background thread."""
        try:
            bundle_path = create_diagnostics_bundle(self._settings_data)
            self.finished.emit(bundle_path, "")
        except Exception as e:
            self.finished.emit("", str(e))


class DiagnosticsDialog(QDialog):
    """Dialog for creating diagnostics bundles for issue reporting."""
    
    def __init__(
        self,
        parent: QWidget | None,
        settings_data: dict[str, object] | None = None
    ) -> None:
        """
        Initialize diagnostics dialog.
        
        Args:
            parent: Parent widget
            settings_data: Optional settings dictionary to include in bundle
        """
        super().__init__(parent)
        
        self._settings_data = settings_data
        self._worker: BundleCreationWorker | None = None
        
        self.setWindowTitle("Report an Issue")
        self.setModal(True)
        self.setMinimumWidth(600)
        self.setMinimumHeight(300)
        
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Title
        title = QLabel("Report an Issue")
        title.setStyleSheet(
            f"font-size: 18px; font-weight: 700; color: {TEXT_PRIMARY};"
        )
        layout.addWidget(title)
        
        # Explanation card
        explanation_card = GlassCard()
        explanation_layout = QVBoxLayout(explanation_card)
        explanation_layout.setContentsMargins(15, 15, 15, 15)
        explanation_layout.setSpacing(10)
        
        explanation = QLabel(
            "This will create a diagnostics bundle containing:\n"
            "\n"
            "• Application version and system information\n"
            "• Recent task logs and state\n"
            "• Application settings\n"
            "\n"
            "All sensitive information (tokens, keys, passwords) will be "
            "automatically redacted.\n"
            "\n"
            "You can attach the generated bundle to your issue report."
        )
        explanation.setWordWrap(True)
        explanation.setStyleSheet(
            f"font-size: 13px; color: {TEXT_PLACEHOLDER}; line-height: 1.5;"
        )
        explanation_layout.addWidget(explanation)
        
        layout.addWidget(explanation_card)
        
        # Status label (initially hidden)
        self._status_label = QLabel()
        self._status_label.setStyleSheet(
            f"font-size: 13px; color: {TEXT_PRIMARY};"
        )
        self._status_label.hide()
        layout.addWidget(self._status_label)
        
        layout.addStretch()
        
        # Button layout
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        
        self._btn_create = QPushButton("Create Diagnostics Bundle")
        self._btn_create.setMinimumHeight(36)
        self._btn_create.clicked.connect(self._create_bundle)
        
        self._btn_open_folder = QPushButton("Open Diagnostics Folder")
        self._btn_open_folder.setMinimumHeight(36)
        self._btn_open_folder.clicked.connect(self._open_folder)
        
        self._btn_close = QPushButton("Close")
        self._btn_close.setMinimumHeight(36)
        self._btn_close.clicked.connect(self.accept)
        
        button_layout.addWidget(self._btn_create)
        button_layout.addWidget(self._btn_open_folder)
        button_layout.addStretch()
        button_layout.addWidget(self._btn_close)
        
        layout.addLayout(button_layout)
    
    def _create_bundle(self) -> None:
        """Create diagnostics bundle in background."""
        if self._worker is not None and self._worker.isRunning():
            return
        
        # Disable buttons during creation
        self._btn_create.setEnabled(False)
        self._btn_open_folder.setEnabled(False)
        
        # Show status
        self._status_label.setText("Creating diagnostics bundle...")
        self._status_label.show()
        
        # Start worker thread
        self._worker = BundleCreationWorker(self._settings_data)
        self._worker.finished.connect(self._on_bundle_created)
        self._worker.start()
    
    def _on_bundle_created(self, bundle_path: str, error: str) -> None:
        """
        Handle bundle creation completion.
        
        Args:
            bundle_path: Path to created bundle, or empty on error
            error: Error message, or empty on success
        """
        # Re-enable buttons
        self._btn_create.setEnabled(True)
        self._btn_open_folder.setEnabled(True)
        
        if error:
            # Show error message
            self._status_label.setText(f"Error: {error}")
            QMessageBox.critical(
                self,
                "Bundle Creation Failed",
                f"Failed to create diagnostics bundle:\n\n{error}"
            )
        else:
            # Show success message
            self._status_label.setText(f"Bundle created: {bundle_path}")
            
            msg = QMessageBox(self)
            msg.setWindowTitle("Bundle Created")
            msg.setText("Diagnostics bundle created successfully.")
            msg.setInformativeText(
                f"Bundle location:\n{bundle_path}\n\n"
                "Would you like to open the bundles folder?"
            )
            msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            msg.setDefaultButton(QMessageBox.Yes)
            
            if msg.exec() == QMessageBox.Yes:
                self._open_folder()
    
    def _open_folder(self) -> None:
        """Open the diagnostics bundles folder in file manager."""
        try:
            folder_path = bundles_dir()
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder_path))
        except Exception as e:
            QMessageBox.warning(
                self,
                "Cannot Open Folder",
                f"Failed to open diagnostics folder:\n\n{str(e)}"
            )
