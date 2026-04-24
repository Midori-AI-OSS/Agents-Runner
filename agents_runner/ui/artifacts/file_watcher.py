"""
File watcher for artifact staging directory.

Provides debounced notifications when files are added, modified, or deleted
in the staging directory during task runtime.
"""

from __future__ import annotations

import errno
import logging
import os
from pathlib import Path

from PySide6.QtCore import (
    QFileSystemWatcher,
    QObject,
    QMetaObject,
    QThread,
    QTimer,
    Qt,
    Signal,
    Slot,
)
from PySide6.QtWidgets import QApplication

logger = logging.getLogger(__name__)
_TRANSIENT_STAGING_ERRNOS = {errno.ENOENT, errno.ENOTDIR}


class ArtifactFileWatcher(QObject):
    """Watch artifact staging directory for changes.

    Emits :attr:`files_changed` when files are added, modified, or deleted.
    Changes are debounced to avoid excessive UI updates.

    Threading:
        Qt timers (and most QObject operations) must be performed from the thread that
        owns the QObject. This watcher is designed to *always* operate in the main Qt
        GUI thread.

        - If constructed from a worker thread, the watcher will automatically move
          itself (and its children) to ``QApplication.instance().thread()``.
        - If a Qt ``parent`` is supplied from a different thread than the constructor
          is running on, parenting is deferred and attached once the watcher is in
          the GUI thread.
        - :meth:`start` and :meth:`stop` are safe to call from any thread; when called
          off-thread they will be queued onto the watcher's owning thread.
    """

    files_changed = Signal()

    def __init__(
        self,
        staging_dir: Path,
        debounce_ms: int = 500,
        parent: QObject | None = None,
    ) -> None:
        requested_parent: QObject | None = None
        current_qt_thread = QThread.currentThread()

        # Prevent Qt cross-thread parenting warnings ("Cannot create children for a
        # parent that is in a different thread") by deferring parenting.
        if parent is not None and parent.thread() is not current_qt_thread:
            requested_parent = parent
            parent = None

        super().__init__(parent)

        app = QApplication.instance()
        gui_thread = app.thread() if app is not None else self.thread()

        if requested_parent is not None and requested_parent.thread() is not gui_thread:
            logger.warning(
                "ArtifactFileWatcher parent is not in the GUI thread; "
                "ignoring parent for thread safety."
            )
            requested_parent = None

        if self.thread() is not gui_thread:
            self.moveToThread(gui_thread)

        self._requested_parent = requested_parent
        if self._requested_parent is not None:
            # Attach on the GUI thread so QObject parenting rules are respected.
            QMetaObject.invokeMethod(self, "_attach_parent", Qt.QueuedConnection)

        self._staging_dir = staging_dir
        self._debounce_ms = debounce_ms
        self._watcher: QFileSystemWatcher | None = None
        self._debounce_timer: QTimer | None = None

        if QThread.currentThread() is not gui_thread:
            # Construct Qt children on the GUI thread to avoid cross-thread parenting
            # warnings ("Cannot create children for a parent that is in a different thread").
            QMetaObject.invokeMethod(self, "_init_qt_objects", Qt.QueuedConnection)
        else:
            self._init_qt_objects()

    @Slot()
    def _attach_parent(self) -> None:
        requested = getattr(self, "_requested_parent", None)
        if requested is None:
            return
        self.setParent(requested)
        self._requested_parent = None

    @Slot()
    def _init_qt_objects(self) -> None:
        if self._watcher is not None and self._debounce_timer is not None:
            return

        self._watcher = QFileSystemWatcher(self)
        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.timeout.connect(self._emit_change)

        # Ensure callbacks that manipulate the debounce timer run on our owning thread.
        self._watcher.directoryChanged.connect(
            self._on_directory_changed, Qt.QueuedConnection
        )
        self._watcher.fileChanged.connect(self._on_file_changed, Qt.QueuedConnection)

    def start(self) -> None:
        """Start watching the staging directory.

        Safe to call from any thread.
        """
        if QThread.currentThread() is not self.thread():
            QMetaObject.invokeMethod(self, "_start_impl", Qt.QueuedConnection)
            return
        self._start_impl()

    @Slot()
    def _start_impl(self) -> None:
        if not self._staging_dir.exists():
            logger.warning(f"Staging directory does not exist: {self._staging_dir}")
            return

        self._init_qt_objects()
        if self._watcher is None:
            return

        self._refresh_watched_directories()

        logger.debug(f"Started watching: {self._staging_dir}")

    def stop(self) -> None:
        """Stop watching.

        Safe to call from any thread.
        """
        if QThread.currentThread() is not self.thread():
            QMetaObject.invokeMethod(self, "_stop_impl", Qt.QueuedConnection)
            return
        self._stop_impl()

    @Slot()
    def _stop_impl(self) -> None:
        # Check if objects were ever initialized before trying to stop them.
        # Don't call _init_qt_objects() here as that would create objects during shutdown.
        if self._debounce_timer is None or self._watcher is None:
            return

        self._debounce_timer.stop()

        paths = self._watcher.directories() + self._watcher.files()
        if paths:
            self._watcher.removePaths(paths)

        logger.debug(f"Stopped watching: {self._staging_dir}")

    def _on_directory_changed(self, path: str) -> None:
        """Directory contents changed (file added/removed)."""
        logger.debug(f"Directory changed: {path}")
        self._refresh_watched_directories()
        self._schedule_emit()

    def _on_file_changed(self, path: str) -> None:
        """File contents modified."""
        logger.debug(f"File changed: {path}")
        self._schedule_emit()

    @Slot()
    def _schedule_emit(self) -> None:
        """Schedule debounced signal emission."""

        # If the debounce timer has not been created yet (e.g. before start
        # or while shutting down), initialize Qt objects from the owning thread.
        if self._debounce_timer is None:
            if QThread.currentThread() is not self.thread():
                QMetaObject.invokeMethod(self, "_schedule_emit", Qt.QueuedConnection)
                return

            self._init_qt_objects()
            if self._debounce_timer is None:
                # Initialization failed or the watcher is being destroyed.
                return
        else:
            # Keep timer start/stop confined to the owning Qt thread.
            if QThread.currentThread() is not self.thread():
                QMetaObject.invokeMethod(self, "_schedule_emit", Qt.QueuedConnection)
                return

        self._debounce_timer.start(self._debounce_ms)

    def _emit_change(self) -> None:
        """Emit files_changed signal."""
        logger.debug("Emitting files_changed signal")
        self.files_changed.emit()

    def _refresh_watched_directories(self) -> None:
        """Update list of watched directories."""
        if not self._staging_dir.exists():
            return

        try:
            watcher = self._watcher
            if watcher is None:
                return

            current_dirs = self._collect_directories()
            watched_dirs = set(watcher.directories())

            new_dirs = current_dirs - watched_dirs
            if new_dirs:
                watcher.addPaths(list(new_dirs))
                logger.debug(f"Added {len(new_dirs)} new directories to watcher")

            removed_dirs = watched_dirs - current_dirs
            if removed_dirs:
                watcher.removePaths(list(removed_dirs))
                logger.debug(
                    f"Removed {len(removed_dirs)} deleted directories from watcher"
                )

        except Exception as e:
            logger.error(f"Failed to refresh watched directories: {e}")

    def _collect_directories(self) -> set[str]:
        """Collect all directories under the staging dir (recursive)."""
        if not self._staging_dir.exists():
            return set()

        directories: set[str] = {str(self._staging_dir)}

        def _on_walk_error(exc: OSError) -> None:
            if int(getattr(exc, "errno", -1)) in _TRANSIENT_STAGING_ERRNOS:
                logger.debug(
                    "Staging walk race while scanning %s: %s",
                    self._staging_dir,
                    exc,
                )
                return
            logger.warning(f"Failed to walk staging dir {self._staging_dir}: {exc}")

        for root, dirnames, _ in os.walk(
            self._staging_dir, followlinks=False, onerror=_on_walk_error
        ):
            root_path = Path(root)
            pruned_dirs: list[str] = []
            for dirname in dirnames:
                dir_path = root_path / dirname
                try:
                    if dir_path.is_symlink():
                        continue
                except Exception:
                    continue
                pruned_dirs.append(dirname)
                directories.add(str(dir_path))
            dirnames[:] = pruned_dirs

        return directories
