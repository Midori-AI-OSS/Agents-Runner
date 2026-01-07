from __future__ import annotations

import logging
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QToolButton, QFileDialog, QSplitter,
)

from agents_runner.artifacts import (
    list_artifacts, decrypt_artifact, ArtifactMeta,
    list_staging_artifacts, get_staging_dir, StagingArtifactMeta
)
from agents_runner.docker.artifact_file_watcher import ArtifactFileWatcher
from agents_runner.ui.task_model import Task
from agents_runner.widgets.glass_card import GlassCard

logger = logging.getLogger(__name__)


def _format_size(size_bytes: int) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


def _format_timestamp(iso_timestamp: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_timestamp)
        return dt.astimezone().strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return iso_timestamp


class ArtifactsTab(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._current_task: Task | None = None
        self._artifacts: list[ArtifactMeta | StagingArtifactMeta] = []
        self._temp_files: list[Path] = []
        self._mode: str = "encrypted"  # "staging" or "encrypted"
        self._file_watcher: ArtifactFileWatcher | None = None
        self._refresh_timer = QTimer()
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.timeout.connect(self._refresh_file_list)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)

        left_panel = GlassCard()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(18, 16, 18, 16)
        left_layout.setSpacing(10)

        list_header = QHBoxLayout()
        list_header.setSpacing(8)
        list_title = QLabel("Artifacts")
        list_title.setStyleSheet("font-size: 14px; font-weight: 650;")
        self._artifact_count = QLabel("(0)")
        self._artifact_count.setStyleSheet("color: rgba(237, 239, 245, 160);")
        
        # Add mode indicator
        self._mode_label = QLabel("Archived Artifacts")
        self._mode_label.setStyleSheet("color: rgba(237, 239, 245, 160); font-size: 11px;")
        
        list_header.addWidget(list_title)
        list_header.addWidget(self._artifact_count)
        list_header.addStretch(1)
        list_header.addWidget(self._mode_label)

        self._artifact_list = QListWidget()
        self._artifact_list.setSpacing(4)
        self._artifact_list.currentRowChanged.connect(self._on_selection_changed)

        left_layout.addLayout(list_header)
        left_layout.addWidget(self._artifact_list, 1)

        right_panel = GlassCard()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(18, 16, 18, 16)
        right_layout.setSpacing(12)

        preview_title = QLabel("Preview")
        preview_title.setStyleSheet("font-size: 14px; font-weight: 650;")

        self._preview_area = QWidget()
        preview_layout = QVBoxLayout(self._preview_area)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.setSpacing(8)

        self._preview_label = QLabel()
        self._preview_label.setAlignment(Qt.AlignCenter)
        self._preview_label.setStyleSheet("color: rgba(237, 239, 245, 160);")
        self._preview_label.setWordWrap(True)

        self._thumbnail = QLabel()
        self._thumbnail.setAlignment(Qt.AlignCenter)
        self._thumbnail.setMinimumSize(200, 200)
        self._thumbnail.hide()

        preview_layout.addStretch(1)
        preview_layout.addWidget(self._preview_label)
        preview_layout.addWidget(self._thumbnail)
        preview_layout.addStretch(1)

        self._empty_state = QLabel("No artifacts collected for this task")
        self._empty_state.setAlignment(Qt.AlignCenter)
        self._empty_state.setStyleSheet(
            "color: rgba(237, 239, 245, 120); font-size: 13px;"
        )
        self._empty_state.setWordWrap(True)

        button_row = QHBoxLayout()
        button_row.setSpacing(8)

        self._btn_open = QToolButton()
        self._btn_open.setText("Open")
        self._btn_open.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self._btn_open.setEnabled(False)
        self._btn_open.clicked.connect(self._on_open_clicked)
        
        self._btn_edit = QToolButton()
        self._btn_edit.setText("Edit")
        self._btn_edit.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self._btn_edit.setEnabled(False)
        self._btn_edit.clicked.connect(self._on_edit_clicked)

        self._btn_download = QToolButton()
        self._btn_download.setText("Download")
        self._btn_download.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self._btn_download.setEnabled(False)
        self._btn_download.clicked.connect(self._on_download_clicked)

        button_row.addStretch(1)
        button_row.addWidget(self._btn_open)
        button_row.addWidget(self._btn_edit)
        button_row.addWidget(self._btn_download)

        right_layout.addWidget(preview_title)
        right_layout.addWidget(self._preview_area, 1)
        right_layout.addWidget(self._empty_state, 1)
        right_layout.addLayout(button_row)

        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)

        layout.addWidget(splitter, 1)

        self._empty_state.show()
        self._preview_area.hide()

    def set_task(self, task: Task) -> None:
        """Load artifacts for a task and determine mode based on status."""
        self._current_task = task
        self._cleanup_temp_files()
        
        # Determine mode based on task status
        if task.status in ["running", "queued"]:
            self._switch_to_staging_mode()
        else:
            self._switch_to_encrypted_mode()
    
    def on_task_status_changed(self, task: Task) -> None:
        """Handle task status changes."""
        if not self._current_task or self._current_task.task_id != task.task_id:
            return
        
        self._current_task = task
        
        # Check if we need to switch modes
        if task.status in ["running", "queued"] and self._mode != "staging":
            self._switch_to_staging_mode()
        elif task.status not in ["running", "queued"] and self._mode == "staging":
            # Task completed - switch to encrypted mode
            self._switch_to_encrypted_mode()
    
    def _switch_to_staging_mode(self) -> None:
        """Switch to staging (live) mode."""
        self._mode = "staging"
        self._mode_label.setText("Live Artifacts")
        self._mode_label.setStyleSheet(
            "color: rgba(100, 255, 100, 200); font-weight: 600; font-size: 11px;"
        )
        
        # Start file watcher
        if self._current_task:
            staging_dir = get_staging_dir(self._current_task.task_id)
            if self._file_watcher:
                self._file_watcher.stop()
            self._file_watcher = ArtifactFileWatcher(staging_dir)
            self._file_watcher.files_changed.connect(self._on_files_changed)
            self._file_watcher.start()
        
        # Load staging artifacts
        self._refresh_file_list()
    
    def _switch_to_encrypted_mode(self) -> None:
        """Switch to encrypted (archived) mode."""
        self._mode = "encrypted"
        self._mode_label.setText("Archived Artifacts")
        self._mode_label.setStyleSheet("color: rgba(237, 239, 245, 160); font-size: 11px;")
        
        # Stop file watcher
        if self._file_watcher:
            self._file_watcher.stop()
            self._file_watcher = None
        
        # Load encrypted artifacts
        if self._current_task:
            self._artifacts = list_artifacts(self._current_task.task_id)
        else:
            self._artifacts = []
        self._update_artifact_list()
    
    def _on_files_changed(self) -> None:
        """Handle file watcher notification (debounced)."""
        # Debounce: Wait 500ms before refreshing
        self._refresh_timer.start(500)
    
    def _refresh_file_list(self) -> None:
        """Refresh artifact list from current mode."""
        if not self._current_task:
            return
        
        if self._mode == "staging":
            self._artifacts = list_staging_artifacts(self._current_task.task_id)
        else:
            self._artifacts = list_artifacts(self._current_task.task_id)
        
        self._update_artifact_list()
    
    def _update_artifact_list(self) -> None:
        """Update UI list widget with current artifacts."""
        self._artifact_list.clear()
        self._artifact_count.setText(f"({len(self._artifacts)})")
    def _update_artifact_list(self) -> None:
        """Update UI list widget with current artifacts."""
        self._artifact_list.clear()
        self._artifact_count.setText(f"({len(self._artifacts)})")

        if not self._artifacts:
            self._empty_state.show()
            self._preview_area.hide()
            self._btn_open.setEnabled(False)
            self._btn_edit.setEnabled(False)
            self._btn_download.setEnabled(False)
            return

        self._empty_state.hide()

        for artifact in self._artifacts:
            item = QListWidgetItem()
            item.setData(Qt.UserRole, artifact)

            widget = QWidget()
            layout = QVBoxLayout(widget)
            layout.setContentsMargins(8, 6, 8, 6)
            layout.setSpacing(2)

            if isinstance(artifact, StagingArtifactMeta):
                # Staging artifact - green color
                name = QLabel(artifact.filename)
                name.setStyleSheet("font-weight: 600; color: rgba(100, 255, 100, 235);")
                
                info_text = f"{_format_size(artifact.size_bytes)} • {_format_timestamp(artifact.modified_at.isoformat())}"
            else:
                # Encrypted artifact - normal color
                name = QLabel(artifact.original_filename)
                name.setStyleSheet("font-weight: 600; color: rgba(237, 239, 245, 235);")
                
                info_text = f"{_format_size(artifact.size_bytes)} • {_format_timestamp(artifact.encrypted_at)}"

            info = QLabel(info_text)
            info.setStyleSheet("font-size: 11px; color: rgba(237, 239, 245, 140);")

            layout.addWidget(name)
            layout.addWidget(info)

            item.setSizeHint(widget.sizeHint())
            self._artifact_list.addItem(item)
            self._artifact_list.setItemWidget(item, widget)

        if self._artifacts:
            self._artifact_list.setCurrentRow(0)

    def _on_selection_changed(self, current_row: int) -> None:
        if current_row < 0 or current_row >= len(self._artifacts):
            self._preview_area.hide()
            self._btn_open.setEnabled(False)
            self._btn_edit.setEnabled(False)
            self._btn_download.setEnabled(False)
            return

        artifact = self._artifacts[current_row]
        self._preview_area.show()
        self._btn_open.setEnabled(True)
        self._thumbnail.hide()
        
        # Enable edit only for staging text files
        if isinstance(artifact, StagingArtifactMeta):
            self._btn_edit.setEnabled(artifact.mime_type.startswith("text/"))
            self._btn_download.setEnabled(False)  # No download for staging
            self._preview_label.setText(f"{artifact.filename}\n{artifact.mime_type}")
            
            if artifact.mime_type.startswith("image/"):
                QTimer.singleShot(0, lambda: self._load_staging_thumbnail(artifact))
        else:
            self._btn_edit.setEnabled(False)  # No edit for encrypted
            self._btn_download.setEnabled(True)
            self._preview_label.setText(f"{artifact.original_filename}\n{artifact.mime_type}")
            
            if artifact.mime_type.startswith("image/"):
                QTimer.singleShot(0, lambda: self._load_thumbnail(artifact))
    
    def _load_staging_thumbnail(self, artifact: StagingArtifactMeta) -> None:
        """Load thumbnail from staging artifact."""
        try:
            pixmap = QPixmap(str(artifact.path))
            if not pixmap.isNull():
                scaled = pixmap.scaled(400, 400, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self._thumbnail.setPixmap(scaled)
                self._thumbnail.show()
            else:
                logger.warning(f"Failed to load image: {artifact.filename}")
        except Exception as e:
            logger.error(f"Failed to load staging thumbnail: {e}")

    def _load_thumbnail(self, artifact: ArtifactMeta) -> None:
        if not self._current_task:
            return

        try:
            suffix = Path(artifact.original_filename).suffix
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp_path = Path(tmp.name)
                self._temp_files.append(tmp_path)

                task_dict = {"task_id": self._current_task.task_id}
                env_name = self._current_task.environment_id or "default"

                if decrypt_artifact(task_dict, env_name, artifact.uuid, tmp_path):
                    pixmap = QPixmap(str(tmp_path))
                    if not pixmap.isNull():
                        scaled = pixmap.scaled(400, 400, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        self._thumbnail.setPixmap(scaled)
                        self._thumbnail.show()
                    else:
                        logger.warning(f"Failed to load image: {artifact.original_filename}")
                else:
                    msg = f"{artifact.original_filename}\n{artifact.mime_type}\n\nFailed to decrypt"
                    self._preview_label.setText(msg)

        except Exception as e:
            logger.error(f"Failed to load thumbnail: {e}")
            msg = f"{artifact.original_filename}\n{artifact.mime_type}\n\nError: {str(e)}"
            self._preview_label.setText(msg)

    def _on_open_clicked(self) -> None:
        current_row = self._artifact_list.currentRow()
        if current_row < 0 or not self._current_task:
            return

        artifact = self._artifacts[current_row]
        
        if isinstance(artifact, StagingArtifactMeta):
            self._open_staging_artifact(artifact)
        else:
            self._open_encrypted_artifact(artifact)
    
    def _open_staging_artifact(self, artifact: StagingArtifactMeta) -> None:
        """Open a staging artifact directly."""
        try:
            file_path = str(artifact.path)
            
            if sys.platform == "darwin":
                subprocess.Popen(["open", file_path])
            elif sys.platform == "win32":
                subprocess.Popen(["start", file_path], shell=True)
            else:
                subprocess.Popen(["xdg-open", file_path])
            
            logger.info(f"Opened staging artifact: {artifact.filename}")
        
        except Exception as e:
            logger.error(f"Failed to open staging artifact: {e}")
    
    def _open_encrypted_artifact(self, artifact: ArtifactMeta) -> None:
        """Open an encrypted artifact (existing implementation)."""
        try:
            suffix = Path(artifact.original_filename).suffix
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp_path = Path(tmp.name)
                self._temp_files.append(tmp_path)

                task_dict = {"task_id": self._current_task.task_id}
                env_name = self._current_task.environment_id or "default"

                if decrypt_artifact(task_dict, env_name, artifact.uuid, tmp_path):
                    if sys.platform == "darwin":
                        subprocess.Popen(["open", str(tmp_path)])
                    elif sys.platform == "win32":
                        subprocess.Popen(["start", str(tmp_path)], shell=True)
                    else:
                        subprocess.Popen(["xdg-open", str(tmp_path)])

                    logger.info(f"Opened artifact: {artifact.original_filename}")
                else:
                    logger.error("Failed to decrypt artifact for opening")

        except Exception as e:
            logger.error(f"Failed to open artifact: {e}")
    
    def _on_edit_clicked(self) -> None:
        """Edit selected artifact in external editor."""
        current_row = self._artifact_list.currentRow()
        if current_row < 0 or not self._current_task:
            return
        
        artifact = self._artifacts[current_row]
        
        # Only allow editing for staging artifacts
        if not isinstance(artifact, StagingArtifactMeta):
            logger.warning("Cannot edit encrypted artifacts")
            return
        
        # Only allow editing for text files
        if not artifact.mime_type.startswith("text/"):
            logger.warning(f"Cannot edit non-text file: {artifact.mime_type}")
            return
        
        self._edit_staging_artifact(artifact)
    
    def _edit_staging_artifact(self, artifact: StagingArtifactMeta) -> None:
        """Launch external editor for a staging artifact."""
        try:
            file_path = str(artifact.path)
            
            # Determine editor command
            if sys.platform == "darwin":
                editor = ["open", "-e"]  # TextEdit on macOS
            elif sys.platform == "win32":
                editor = ["notepad.exe"]  # Notepad on Windows
            else:
                # Linux: Try $EDITOR, fall back to xdg-open
                import os
                editor_env = os.environ.get("EDITOR")
                if editor_env:
                    editor = [editor_env]
                else:
                    editor = ["xdg-open"]
            
            # Launch editor (non-blocking)
            subprocess.Popen(editor + [file_path])
            
            logger.info(f"Launched editor for: {artifact.filename}")
        
        except Exception as e:
            logger.error(f"Failed to launch editor: {e}")

    def _on_download_clicked(self) -> None:
        current_row = self._artifact_list.currentRow()
        if current_row < 0 or not self._current_task:
            return

        artifact = self._artifacts[current_row]
        dest_path, _ = QFileDialog.getSaveFileName(
            self, "Save Artifact", artifact.original_filename, "All Files (*.*)"
        )

        if not dest_path:
            return

        try:
            task_dict = {"task_id": self._current_task.task_id}
            env_name = self._current_task.environment_id or "default"

            if decrypt_artifact(task_dict, env_name, artifact.uuid, dest_path):
                logger.info(f"Downloaded artifact to: {dest_path}")
            else:
                logger.error("Failed to decrypt artifact for download")

        except Exception as e:
            logger.error(f"Failed to download artifact: {e}")

    def _cleanup_temp_files(self) -> None:
        for tmp_path in self._temp_files:
            try:
                if tmp_path.exists():
                    tmp_path.unlink()
            except Exception as e:
                logger.debug(f"Failed to cleanup temp file {tmp_path}: {e}")
        self._temp_files.clear()

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        self._cleanup_temp_files()
        # Stop file watcher when tab is hidden
        if self._file_watcher:
            self._file_watcher.stop()
            self._file_watcher = None
