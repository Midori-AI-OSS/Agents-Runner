from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QObject, QEvent, Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QToolButton, QFileDialog, QSplitter, QPlainTextEdit,
    QSizePolicy,
)

from agents_runner.artifacts import (
    list_artifacts, ArtifactMeta,
    list_staging_artifacts, get_staging_dir, StagingArtifactMeta
)
from agents_runner.docker.artifact_file_watcher import ArtifactFileWatcher
from agents_runner.ui.task_model import Task
from agents_runner.ui.pages.artifacts_utils import (
    format_size, format_timestamp, PreviewLoader,
    open_staging_artifact, open_encrypted_artifact,
    edit_staging_artifact, download_artifact, cleanup_temp_files
)
from agents_runner.widgets.glass_card import GlassCard
from agents_runner.widgets.artifact_highlighter import ArtifactSyntaxHighlighter

logger = logging.getLogger(__name__)


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
        self._preview_loader: PreviewLoader | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)

        left_panel = GlassCard()
        left_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
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
        right_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(18, 16, 18, 16)
        right_layout.setSpacing(12)

        preview_title = QLabel("Preview")
        preview_title.setStyleSheet("font-size: 14px; font-weight: 650;")

        self._preview_area = QWidget()
        self._preview_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        preview_layout = QVBoxLayout(self._preview_area)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.setSpacing(8)

        self._preview_label = QLabel()
        self._preview_label.setAlignment(Qt.AlignCenter)
        self._preview_label.setStyleSheet("color: rgba(237, 239, 245, 160);")
        self._preview_label.setWordWrap(True)
        self._preview_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self._thumbnail = QLabel()
        self._thumbnail.setAlignment(Qt.AlignCenter)
        self._thumbnail.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._thumbnail.setMinimumSize(1, 1)
        self._thumbnail.installEventFilter(self)
        self._thumbnail.hide()

        self._text_preview = QPlainTextEdit()
        self._text_preview.setReadOnly(True)
        self._text_preview.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self._text_preview.setMaximumBlockCount(5000)
        self._text_preview.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        # Set monospace font
        font = QFont("Monospace", 9)
        font.setStyleHint(QFont.StyleHint.TypeWriter)
        self._text_preview.setFont(font)
        
        self._text_preview.hide()
        
        # Syntax highlighter (created on demand)
        self._syntax_highlighter: ArtifactSyntaxHighlighter | None = None
        
        # Initialize preview loader
        self._preview_loader = PreviewLoader(
            self._preview_label,
            self._thumbnail,
            self._text_preview,
            self._syntax_highlighter
        )

        preview_layout.addWidget(self._preview_label)
        preview_layout.addWidget(self._thumbnail, 1)
        preview_layout.addWidget(self._text_preview, 1)

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

    def showEvent(self, event) -> None:
        super().showEvent(event)
        QTimer.singleShot(0, self._refresh_file_list)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched is self._thumbnail and event.type() == QEvent.Type.Resize:
            if self._preview_loader:
                self._preview_loader.update_thumbnail_scale()
        return super().eventFilter(watched, event)

    def set_task(self, task: Task) -> None:
        """Load artifacts for a task and determine mode based on status."""
        self._current_task = task
        cleanup_temp_files(self._temp_files)
        if self._preview_loader:
            self._preview_loader.cleanup_temp_files()
        
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
        elif self._mode == "encrypted":
            # Artifacts are finalized asynchronously after task completion; refresh when
            # the task model gains archived artifact UUIDs.
            expected = len(task.artifacts or [])
            if expected > 0 and len(self._artifacts) != expected:
                QTimer.singleShot(0, self._refresh_file_list)
    
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

        if not self._artifacts:
            # Update empty state message based on mode
            if self._mode == "staging" and self._current_task:
                staging_dir = get_staging_dir(self._current_task.task_id)
                self._empty_state.setText(
                    f"No artifacts yet\n\nWatching: {staging_dir}"
                )
            else:
                self._empty_state.setText("No artifacts collected for this task")
            
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
                
                info_text = f"{format_size(artifact.size_bytes)} • {format_timestamp(artifact.modified_at.isoformat())}"
            else:
                # Encrypted artifact - normal color
                name = QLabel(artifact.original_filename)
                name.setStyleSheet("font-weight: 600; color: rgba(237, 239, 245, 235);")
                
                info_text = f"{format_size(artifact.size_bytes)} • {format_timestamp(artifact.encrypted_at)}"

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
        
        # Reset preview widgets
        self._thumbnail.hide()
        self._text_preview.hide()
        self._preview_label.show()
        if self._preview_loader:
            self._preview_loader.thumbnail_original = None
        
        # Enable edit only for staging text files
        if isinstance(artifact, StagingArtifactMeta):
            self._btn_edit.setEnabled(artifact.mime_type.startswith("text/"))
            self._btn_download.setEnabled(False)  # No download for staging
            
            # Determine preview type
            if artifact.mime_type.startswith("text/"):
                # Load and display text content inline
                QTimer.singleShot(0, lambda: self._load_staging_text(artifact))
            elif artifact.mime_type in ("image/png", "image/jpeg", "image/jpg", "image/webp"):
                # Load and display image thumbnail
                self._preview_label.setText(f"{artifact.filename}\n{artifact.mime_type}")
                QTimer.singleShot(0, lambda: self._load_staging_thumbnail(artifact))
            else:
                # Show info only, keep Open button as fallback
                self._preview_label.setText(
                    f"{artifact.filename}\n{artifact.mime_type}\n\n"
                    f"Size: {format_size(artifact.size_bytes)}\n"
                    "Use 'Open' button to view"
                )
        else:
            self._btn_edit.setEnabled(False)  # No edit for encrypted
            self._btn_download.setEnabled(True)
            
            # Determine preview type
            if artifact.mime_type.startswith("text/"):
                # Load and display text content inline
                QTimer.singleShot(0, lambda: self._load_encrypted_text(artifact))
            elif artifact.mime_type in ("image/png", "image/jpeg", "image/jpg", "image/webp"):
                # Load and display image thumbnail
                self._preview_label.setText(f"{artifact.original_filename}\n{artifact.mime_type}")
                QTimer.singleShot(0, lambda: self._load_thumbnail(artifact))
            else:
                # Show info only, keep Open button as fallback
                self._preview_label.setText(
                    f"{artifact.original_filename}\n{artifact.mime_type}\n\n"
                    f"Size: {format_size(artifact.size_bytes)}\n"
                    "Use 'Open' button to view"
                )
    
    def _load_staging_thumbnail(self, artifact: StagingArtifactMeta) -> None:
        """Load thumbnail from staging artifact."""
        if self._preview_loader:
            self._preview_loader.load_staging_thumbnail(artifact)

    def _load_thumbnail(self, artifact: ArtifactMeta) -> None:
        """Load thumbnail from encrypted artifact."""
        if not self._current_task or not self._preview_loader:
            return
        self._preview_loader.load_encrypted_thumbnail(
            artifact,
            self._current_task.task_id,
            self._current_task.environment_id
        )
    
    def _load_staging_text(self, artifact: StagingArtifactMeta) -> None:
        """Load text content from staging artifact."""
        if self._preview_loader:
            self._preview_loader.load_staging_text(artifact)
    
    def _load_encrypted_text(self, artifact: ArtifactMeta) -> None:
        """Load text content from encrypted artifact."""
        if not self._current_task or not self._preview_loader:
            return
        self._preview_loader.load_encrypted_text(
            artifact,
            self._current_task.task_id,
            self._current_task.environment_id
        )

    def _on_open_clicked(self) -> None:
        current_row = self._artifact_list.currentRow()
        if current_row < 0 or not self._current_task:
            return

        artifact = self._artifacts[current_row]
        
        if isinstance(artifact, StagingArtifactMeta):
            open_staging_artifact(artifact)
        else:
            open_encrypted_artifact(
                artifact,
                self._current_task.task_id,
                self._current_task.environment_id,
                self._temp_files
            )
    
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
        
        edit_staging_artifact(artifact)

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

        download_artifact(
            artifact,
            self._current_task.task_id,
            self._current_task.environment_id,
            dest_path
        )

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        cleanup_temp_files(self._temp_files)
        if self._preview_loader:
            self._preview_loader.cleanup_temp_files()
        # Stop file watcher when tab is hidden
        if self._file_watcher:
            self._file_watcher.stop()
            self._file_watcher = None
