from __future__ import annotations

import logging
import os
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel, QPlainTextEdit

from agents_runner.artifacts import (
    decrypt_artifact, ArtifactMeta, StagingArtifactMeta
)
from agents_runner.widgets.artifact_highlighter import ArtifactSyntaxHighlighter, detect_language

logger = logging.getLogger(__name__)


def format_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


def format_timestamp(iso_timestamp: str) -> str:
    """Format ISO timestamp to human-readable format."""
    try:
        dt = datetime.fromisoformat(iso_timestamp)
        return dt.astimezone().strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return iso_timestamp


class PreviewLoader:
    """Helper class for loading artifact previews."""
    
    def __init__(
        self,
        preview_label: QLabel,
        thumbnail_widget: QLabel,
        text_preview: QPlainTextEdit,
        syntax_highlighter: ArtifactSyntaxHighlighter | None = None
    ):
        self.preview_label = preview_label
        self.thumbnail_widget = thumbnail_widget
        self.text_preview = text_preview
        self.syntax_highlighter = syntax_highlighter
        self.thumbnail_original: QPixmap | None = None
        self.temp_files: list[Path] = []
    
    def cleanup_temp_files(self) -> None:
        """Clean up temporary files."""
        for tmp_path in self.temp_files:
            try:
                if tmp_path.exists():
                    tmp_path.unlink()
            except Exception as e:
                logger.debug(f"Failed to cleanup temp file {tmp_path}: {e}")
        self.temp_files.clear()
    
    def update_thumbnail_scale(self) -> None:
        """Update thumbnail to fit current widget size."""
        if self.thumbnail_original is None:
            return
        target_size = self.thumbnail_widget.contentsRect().size()
        if target_size.isEmpty():
            return
        from PySide6.QtCore import Qt
        scaled = self.thumbnail_original.scaled(
            target_size, Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self.thumbnail_widget.setPixmap(scaled)
    
    def load_staging_thumbnail(self, artifact: StagingArtifactMeta) -> None:
        """Load thumbnail from staging artifact."""
        try:
            pixmap = QPixmap(str(artifact.path))
            if not pixmap.isNull():
                self.thumbnail_original = pixmap
                self.update_thumbnail_scale()
                self.thumbnail_widget.show()
            else:
                logger.warning(f"Failed to load image: {artifact.filename}")
        except Exception as e:
            logger.error(f"Failed to load staging thumbnail: {e}")
    
    def load_encrypted_thumbnail(
        self,
        artifact: ArtifactMeta,
        task_id: str,
        environment_id: str | None
    ) -> None:
        """Load thumbnail from encrypted artifact."""
        try:
            suffix = Path(artifact.original_filename).suffix
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp_path = Path(tmp.name)
                self.temp_files.append(tmp_path)

                task_dict = {"task_id": task_id}
                env_name = environment_id or "default"

                if decrypt_artifact(task_dict, env_name, artifact.uuid, tmp_path):
                    pixmap = QPixmap(str(tmp_path))
                    if not pixmap.isNull():
                        self.thumbnail_original = pixmap
                        self.update_thumbnail_scale()
                        self.thumbnail_widget.show()
                    else:
                        logger.warning(f"Failed to load image: {artifact.original_filename}")
                else:
                    msg = f"{artifact.original_filename}\n{artifact.mime_type}\n\nFailed to decrypt"
                    self.preview_label.setText(msg)

        except Exception as e:
            logger.error(f"Failed to load thumbnail: {e}")
            msg = f"{artifact.original_filename}\n{artifact.mime_type}\n\nError: {str(e)}"
            self.preview_label.setText(msg)
    
    def load_staging_text(self, artifact: StagingArtifactMeta) -> None:
        """Load text content from staging artifact."""
        try:
            max_size = 1024 * 1024  # 1MB limit
            if artifact.size_bytes > max_size:
                self.preview_label.setText(
                    f"{artifact.filename}\n{artifact.mime_type}\n\n"
                    f"File too large ({format_size(artifact.size_bytes)})\n"
                    "Use 'Open' button to view externally"
                )
                self.preview_label.show()
                return
            
            # Check for binary content
            sample_size = min(8192, artifact.size_bytes)
            with open(artifact.path, "rb") as f:
                sample = f.read(sample_size)
            
            if b"\x00" in sample:
                # Binary file detected
                self.preview_label.setText(
                    f"{artifact.filename}\n{artifact.mime_type}\n\n"
                    "Binary file detected\n"
                    "Use 'Open' button to view externally"
                )
                self.preview_label.show()
                return
            
            # Load text content
            text = artifact.path.read_text(encoding='utf-8', errors='replace')
            self.text_preview.setPlainText(text)
            
            # Apply syntax highlighting if file is small enough
            highlight_threshold = 100 * 1024  # 100KB
            if artifact.size_bytes <= highlight_threshold:
                language = detect_language(artifact.filename, text[:1024])
                if language != "text":
                    if not self.syntax_highlighter:
                        self.syntax_highlighter = ArtifactSyntaxHighlighter(
                            self.text_preview.document()
                        )
                    self.syntax_highlighter.set_language(language)
                elif self.syntax_highlighter:
                    # Clear highlighter for plain text
                    self.syntax_highlighter.set_language("text")
            elif self.syntax_highlighter:
                # Disable highlighting for large files
                self.syntax_highlighter.set_language("text")
            
            self.text_preview.show()
            self.preview_label.hide()
        except Exception as e:
            logger.error(f"Failed to load text: {e}")
            self.preview_label.setText(f"{artifact.filename}\n\nError loading text: {str(e)}")
            self.preview_label.show()
    
    def load_encrypted_text(
        self,
        artifact: ArtifactMeta,
        task_id: str,
        environment_id: str | None
    ) -> None:
        """Load text content from encrypted artifact."""
        try:
            max_size = 1024 * 1024  # 1MB limit
            if artifact.size_bytes > max_size:
                self.preview_label.setText(
                    f"{artifact.original_filename}\n{artifact.mime_type}\n\n"
                    f"File too large ({format_size(artifact.size_bytes)})\n"
                    "Use 'Open' button to view externally"
                )
                self.preview_label.show()
                return
            
            suffix = Path(artifact.original_filename).suffix
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp_path = Path(tmp.name)
                self.temp_files.append(tmp_path)

                task_dict = {"task_id": task_id}
                env_name = environment_id or "default"

                if decrypt_artifact(task_dict, env_name, artifact.uuid, tmp_path):
                    # Check for binary content
                    sample_size = min(8192, artifact.size_bytes)
                    with open(tmp_path, "rb") as f:
                        sample = f.read(sample_size)
                    
                    if b"\x00" in sample:
                        # Binary file detected
                        self.preview_label.setText(
                            f"{artifact.original_filename}\n{artifact.mime_type}\n\n"
                            "Binary file detected\n"
                            "Use 'Open' button to view externally"
                        )
                        self.preview_label.show()
                        return
                    
                    # Load text content
                    text = tmp_path.read_text(encoding='utf-8', errors='replace')
                    self.text_preview.setPlainText(text)
                    
                    # Apply syntax highlighting if file is small enough
                    highlight_threshold = 100 * 1024  # 100KB
                    if artifact.size_bytes <= highlight_threshold:
                        language = detect_language(artifact.original_filename, text[:1024])
                        if language != "text":
                            if not self.syntax_highlighter:
                                self.syntax_highlighter = ArtifactSyntaxHighlighter(
                                    self.text_preview.document()
                                )
                            self.syntax_highlighter.set_language(language)
                        elif self.syntax_highlighter:
                            # Clear highlighter for plain text
                            self.syntax_highlighter.set_language("text")
                    elif self.syntax_highlighter:
                        # Disable highlighting for large files
                        self.syntax_highlighter.set_language("text")
                    
                    self.text_preview.show()
                    self.preview_label.hide()
                else:
                    msg = f"{artifact.original_filename}\n{artifact.mime_type}\n\nFailed to decrypt"
                    self.preview_label.setText(msg)
                    self.preview_label.show()

        except Exception as e:
            logger.error(f"Failed to load encrypted text: {e}")
            msg = f"{artifact.original_filename}\n{artifact.mime_type}\n\nError: {str(e)}"
            self.preview_label.setText(msg)
            self.preview_label.show()


def open_staging_artifact(artifact: StagingArtifactMeta) -> None:
    """Open a staging artifact directly."""
    try:
        file_path = str(artifact.path)
        
        if sys.platform == "darwin":
            subprocess.Popen(["open", file_path])
        elif sys.platform == "win32":
            os.startfile(file_path)
        else:
            subprocess.Popen(["xdg-open", file_path])
        
        logger.info(f"Opened staging artifact: {artifact.filename}")
    
    except Exception as e:
        logger.error(f"Failed to open staging artifact: {e}")


def open_encrypted_artifact(
    artifact: ArtifactMeta,
    task_id: str,
    environment_id: str | None,
    temp_files: list[Path]
) -> None:
    """Open an encrypted artifact."""
    try:
        suffix = Path(artifact.original_filename).suffix
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp_path = Path(tmp.name)
            temp_files.append(tmp_path)

            task_dict = {"task_id": task_id}
            env_name = environment_id or "default"

            if decrypt_artifact(task_dict, env_name, artifact.uuid, tmp_path):
                if sys.platform == "darwin":
                    subprocess.Popen(["open", str(tmp_path)])
                elif sys.platform == "win32":
                    os.startfile(str(tmp_path))
                else:
                    subprocess.Popen(["xdg-open", str(tmp_path)])

                logger.info(f"Opened artifact: {artifact.original_filename}")
            else:
                logger.error("Failed to decrypt artifact for opening")

    except Exception as e:
        logger.error(f"Failed to open artifact: {e}")


def edit_staging_artifact(artifact: StagingArtifactMeta) -> None:
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


def download_artifact(
    artifact: ArtifactMeta,
    task_id: str,
    environment_id: str | None,
    dest_path: str
) -> bool:
    """Download and decrypt an artifact to the specified path."""
    try:
        task_dict = {"task_id": task_id}
        env_name = environment_id or "default"

        if decrypt_artifact(task_dict, env_name, artifact.uuid, dest_path):
            logger.info(f"Downloaded artifact to: {dest_path}")
            return True
        else:
            logger.error("Failed to decrypt artifact for download")
            return False

    except Exception as e:
        logger.error(f"Failed to download artifact: {e}")
        return False


def cleanup_temp_files(temp_files: list[Path]) -> None:
    """Clean up temporary files."""
    for tmp_path in temp_files:
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except Exception as e:
            logger.debug(f"Failed to cleanup temp file {tmp_path}: {e}")
    temp_files.clear()
