"""
File watcher for artifact staging directory.

Provides debounced notifications when files are added, modified, or deleted
in the staging directory during task runtime.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QFileSystemWatcher, QObject, QTimer, Signal

logger = logging.getLogger(__name__)


class ArtifactFileWatcher(QObject):
    """
    Watch artifact staging directory for changes.
    
    Emits files_changed signal when files are added, modified, or deleted.
    Changes are debounced to avoid excessive UI updates.
    """
    
    files_changed = Signal()
    
    def __init__(self, staging_dir: Path, debounce_ms: int = 500, parent: QObject | None = None) -> None:
        """
        Initialize file watcher.
        
        Args:
            staging_dir: Path to staging directory to watch
            debounce_ms: Debounce delay in milliseconds (default 500ms)
            parent: Parent QObject for proper Qt lifecycle and thread affinity
        """
        super().__init__(parent)
        self._staging_dir = staging_dir
        self._watcher = QFileSystemWatcher(self)
        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.timeout.connect(self._emit_change)
        self._debounce_ms = debounce_ms
        
        # Connect watcher signals
        self._watcher.directoryChanged.connect(self._on_directory_changed)
        self._watcher.fileChanged.connect(self._on_file_changed)
    
    def start(self) -> None:
        """Start watching the staging directory."""
        if not self._staging_dir.exists():
            logger.warning(f"Staging directory does not exist: {self._staging_dir}")
            return
        
        # Watch directory
        self._watcher.addPath(str(self._staging_dir))
        
        # Watch existing files
        try:
            for file_path in self._staging_dir.iterdir():
                if file_path.is_file():
                    self._watcher.addPath(str(file_path))
        except Exception as e:
            logger.error(f"Failed to add initial files to watcher: {e}")
        
        logger.debug(f"Started watching: {self._staging_dir}")
    
    def stop(self) -> None:
        """Stop watching."""
        self._debounce_timer.stop()
        
        paths = self._watcher.directories() + self._watcher.files()
        if paths:
            self._watcher.removePaths(paths)
        
        logger.debug(f"Stopped watching: {self._staging_dir}")
    
    def _on_directory_changed(self, path: str) -> None:
        """Directory contents changed (file added/removed)."""
        logger.debug(f"Directory changed: {path}")
        self._refresh_watched_files()
        self._schedule_emit()
    
    def _on_file_changed(self, path: str) -> None:
        """File contents modified."""
        logger.debug(f"File changed: {path}")
        self._schedule_emit()
    
    def _schedule_emit(self) -> None:
        """Schedule debounced signal emission."""
        self._debounce_timer.start(self._debounce_ms)
    
    def _emit_change(self) -> None:
        """Emit files_changed signal."""
        logger.debug("Emitting files_changed signal")
        self.files_changed.emit()
    
    def _refresh_watched_files(self) -> None:
        """Update list of watched files."""
        if not self._staging_dir.exists():
            return
        
        try:
            current_files = {
                str(f) for f in self._staging_dir.iterdir() if f.is_file()
            }
            watched_files = set(self._watcher.files())
            
            # Add new files
            new_files = current_files - watched_files
            if new_files:
                self._watcher.addPaths(list(new_files))
                logger.debug(f"Added {len(new_files)} new files to watcher")
            
            # Remove deleted files
            deleted_files = watched_files - current_files
            if deleted_files:
                self._watcher.removePaths(list(deleted_files))
                logger.debug(f"Removed {len(deleted_files)} deleted files from watcher")
        
        except Exception as e:
            logger.error(f"Failed to refresh watched files: {e}")
