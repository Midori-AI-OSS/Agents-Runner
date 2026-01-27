# Task: Fix ArtifactFileWatcher Thread Affinity

**Issue:** #141  
**Target File:** `agents_runner/docker/artifact_file_watcher.py`  
**Type:** Bug Fix  
**Depends On:** Task 141-01

## Objective
Ensure ArtifactFileWatcher and its QTimer are always created and operated in the main Qt GUI thread.

## Context
Qt timers must be started/stopped from the same thread that created the QObject. The warnings indicate the watcher or its timers are being manipulated from worker threads.

## Task
Modify `ArtifactFileWatcher` to ensure thread-safe operation:
1. Verify the `parent` QObject parameter is always from the main thread
2. If created in a non-main thread, use `moveToThread(QApplication.instance().thread())` after construction
3. Ensure `start()` and `stop()` are called only from the main thread or use `QMetaObject.invokeMethod()` with `Qt.QueuedConnection`
4. Update docstrings to clarify thread requirements

## Acceptance Criteria
- [x] ArtifactFileWatcher reliably operates in the main GUI thread
- [x] No Qt timer cross-thread warnings when running `uv run main.py`
- [x] Existing file watching functionality preserved
- [x] No new crashes or hangs introduced

## Completion Notes
- Updated `ArtifactFileWatcher` to enforce GUI-thread affinity:
  - Defers cross-thread parenting and attaches parent on GUI thread
  - Moves watcher QObject to `QApplication.instance().thread()` if needed
  - Creates `QFileSystemWatcher` and `QTimer` on the GUI thread (deferred init)
  - Queues `start()`/`stop()` calls to the owning thread via `QMetaObject.invokeMethod(..., Qt.QueuedConnection)`
- Verification: ran `uv run main.py` and observed no `QObject::startTimer` / `QObject::killTimer` warnings (GUI run for ~15s).

## Commits
- f0f0d2e `[FIX] Ensure watcher runs in GUI thread`
