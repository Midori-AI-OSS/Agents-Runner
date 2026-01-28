# Crash exit 139 — code locations / paths (brainstorm)

## Desktop tab lifecycle + URL navigation

- `agents_runner/ui/pages/task_details.py`
  - `TaskDetailsPage.__init__`: creates `_desktop_web = QWebEngineView()` immediately (if QtWebEngine import succeeds).
  - `TaskDetailsPage._on_tab_changed`: schedules `_maybe_load_desktop` when Desktop tab selected.
  - `TaskDetailsPage._maybe_load_desktop`: calls `self._desktop_web.setUrl(QUrl(url))` for `task.novnc_url`.
  - `TaskDetailsPage._sync_desktop`:
    - Shows/hides Desktop tab dynamically based on `task.is_active()`, `task.headless_desktop_enabled`, and `task.novnc_url`.
    - When hiding, it attempts `self._desktop_web.setUrl(QUrl("about:blank"))`.

## Task opening pathway (where a crash is reported)

- `agents_runner/ui/main_window_task_events.py`
  - `_open_task_details(...)` loads task payload and calls `self._details.show_task(task)`.
- `agents_runner/ui/pages/task_details.py`
  - `show_task(...)` calls `_sync_desktop(task)` (and sets current tab index).

## “Startup initialization” vs “lazy navigation”

- `agents_runner/app.py`
  - `_initialize_qtwebengine()` creates a hidden `QWebEngineView()` dummy to “force Chromium initialization”.
  - `_configure_qtwebengine_runtime()` only disables GPU/Vulkan if `/dev/dri` does *not* exist.
- `agents_runner/ui/main_window.py`
  - `MainWindow.__init__` constructs `TaskDetailsPage()` on app startup (even if the page is hidden).

## Notes

- Even though `TaskDetailsPage` (and its `QWebEngineView`) are constructed at startup, the noVNC page itself is still loaded lazily: navigation happens only when a task has a non-empty `novnc_url` and the Desktop tab becomes active.
- If “Desktop should load on program startup” means “start QtWebEngine/Chromium early”, the app already tries via `_initialize_qtwebengine()` and eager `QWebEngineView()` construction; if it means “pre-navigate to warm up the renderer/network stack”, current code does not do that.
