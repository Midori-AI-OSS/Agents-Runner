from __future__ import annotations

import logging
import tempfile
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QToolButton, QFileDialog, QSplitter,
)

from agents_runner.artifacts import list_artifacts, decrypt_artifact, ArtifactMeta
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
        self._artifacts: list[ArtifactMeta] = []
        self._temp_files: list[Path] = []

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
        list_header.addWidget(list_title)
        list_header.addWidget(self._artifact_count)
        list_header.addStretch(1)

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

        self._btn_download = QToolButton()
        self._btn_download.setText("Download")
        self._btn_download.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self._btn_download.setEnabled(False)
        self._btn_download.clicked.connect(self._on_download_clicked)

        button_row.addStretch(1)
        button_row.addWidget(self._btn_open)
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
        self._current_task = task
        self._cleanup_temp_files()
        self._artifacts = list_artifacts(task.task_id)
        self._artifact_list.clear()
        self._artifact_count.setText(f"({len(self._artifacts)})")

        if not self._artifacts:
            self._empty_state.show()
            self._preview_area.hide()
            self._btn_open.setEnabled(False)
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

            name = QLabel(artifact.original_filename)
            name.setStyleSheet("font-weight: 600; color: rgba(237, 239, 245, 235);")

            info = QLabel(f"{_format_size(artifact.size_bytes)} • {_format_timestamp(artifact.encrypted_at)}")
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
            self._btn_download.setEnabled(False)
            return

        artifact = self._artifacts[current_row]
        self._preview_area.show()
        self._btn_open.setEnabled(True)
        self._btn_download.setEnabled(True)
        self._thumbnail.hide()
        self._preview_label.setText(f"{artifact.original_filename}\n{artifact.mime_type}")

        if artifact.mime_type.startswith("image/"):
            QTimer.singleShot(0, lambda a=artifact: self._load_thumbnail(a))

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
        if current_row < 0 or current_row >= len(self._artifacts) or not self._current_task:
            return

        artifact = self._artifacts[current_row]

        try:
            suffix = Path(artifact.original_filename).suffix
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp_path = Path(tmp.name)
                self._temp_files.append(tmp_path)

                task_dict = {"task_id": self._current_task.task_id}
                env_name = self._current_task.environment_id or "default"

                if decrypt_artifact(task_dict, env_name, artifact.uuid, tmp_path):
                    import subprocess
                    import sys

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

    def _on_download_clicked(self) -> None:
        current_row = self._artifact_list.currentRow()
        if current_row < 0 or current_row >= len(self._artifacts) or not self._current_task:
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
