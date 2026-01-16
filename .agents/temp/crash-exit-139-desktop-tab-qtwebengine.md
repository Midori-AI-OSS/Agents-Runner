# Task — Investigate intermittent exit `139` when opening task / switching to Desktop tab (QtWebEngine)

## 1. Title (short)
Intermittent segfault (`139`) tied to Desktop tab / task open

## 2. Summary (1–3 sentences)
The GUI sometimes terminates with exit code `139` (SIGSEGV) while opening a task or switching to the `Desktop` tab. This appears strongly correlated with QtWebEngine (`QWebEngineView`) navigation (`setUrl(...)`) and/or GPU/fontconfig setup during Chromium initialization. This task is investigation + stabilization planning only (do not implement fixes here).

## 3. Observed symptoms / repro hints
- Running the app can print Chromium/QtWebEngine startup messages like:
  - `GBM is not supported with the current configuration. Fallback to Vulkan rendering in Chromium.`
  - `Fontconfig error: Cannot load default config file: No such file: (null)`
- Crash triggers reported:
  - Selecting/opening a task in the dashboard (transitions to Task Details view).
  - Clicking the `Desktop` tab (noVNC embed) or switching back/forth between tabs.
- Exit code `139` implies a hard crash (segfault) in native code; Python exceptions may not surface.

## 4. Code locations strongly associated with the crash path

### Desktop tab lifecycle + URL navigation
- `agents_runner/ui/pages/task_details.py`
  - `TaskDetailsPage.__init__`: creates `_desktop_web = QWebEngineView()` immediately (if QtWebEngine import succeeds).
  - `TaskDetailsPage._on_tab_changed`: schedules `_maybe_load_desktop` when Desktop tab selected.
  - `TaskDetailsPage._maybe_load_desktop`: calls `self._desktop_web.setUrl(QUrl(url))` for `task.novnc_url`.
  - `TaskDetailsPage._sync_desktop`:
    - Shows/hides Desktop tab dynamically based on `task.is_active()`, `task.headless_desktop_enabled`, and `task.novnc_url`.
    - When hiding, it attempts `self._desktop_web.setUrl(QUrl("about:blank"))`.

### Task opening pathway (where a crash is reported)
- `agents_runner/ui/main_window_task_events.py`
  - `_open_task_details(...)` loads task payload and calls `self._details.show_task(task)`.
- `agents_runner/ui/pages/task_details.py`
  - `show_task(...)` calls `_sync_desktop(task)` (and sets current tab index).

### “Startup initialization” vs “lazy navigation”
- `agents_runner/app.py`
  - `_initialize_qtwebengine()` creates a hidden `QWebEngineView()` dummy to “force Chromium initialization”.
  - `_configure_qtwebengine_runtime()` only disables GPU/Vulkan if `/dev/dri` does *not* exist.
- `agents_runner/ui/main_window.py`
  - `MainWindow.__init__` constructs `TaskDetailsPage()` on app startup (even if the page is hidden).

Notes:
- Even though `TaskDetailsPage` (and its `QWebEngineView`) are constructed at startup, the noVNC page itself is still loaded lazily: navigation happens only when a task has a non-empty `novnc_url` and the Desktop tab becomes active.
- If “Desktop should load on program startup” means “start QtWebEngine/Chromium early”, the app already tries via `_initialize_qtwebengine()` and eager `QWebEngineView()` construction; if it means “pre-navigate to warm up the renderer/network stack”, current code does not do that.

## 5. Hypotheses (what could be happening)
1. **QtWebEngine/Chromium GPU path instability**: startup logs mention GBM unsupported and Vulkan fallback; GPU acceleration may be active because `_configure_qtwebengine_runtime()` disables GPU only when `/dev/dri` is absent, but `/dev/dri` can exist while GBM is unusable.
2. **Fontconfig initialization issue**: the `Fontconfig error ... (null)` suggests the QtWebEngine subprocess may not be finding a valid fontconfig config (or is running with a sanitized env). This could be benign or could contribute to instability/crashes in Chromium initialization or rendering.
3. **Navigation timing / widget visibility**: `setUrl(...)` occurs via `QTimer.singleShot(0, ...)` on tab change; combined with rapid tab switching, tab add/remove, or task switching, this might race native code paths inside QtWebEngine.
4. **Repeated `setUrl(about:blank)` during tab hiding**: opening a task (or updates via `_details.update_task`) can trigger `_sync_desktop`, which may switch URLs even when the view is hidden; QtWebEngine sometimes has fragile teardown/reload behavior.
5. **Two separate “initialization” touches**: `_initialize_qtwebengine()` creates + schedules deletion of a dummy view, while `TaskDetailsPage` creates the real view; creation/destruction before the event loop starts might still leave partially initialized state (worth validating).
6. **Desktop tab “reload” is currently expected**: `_sync_desktop()` explicitly navigates the Desktop `QWebEngineView` to `about:blank` and clears `_desktop_loaded_url` when the tab is hidden (or desktop is not ready). Returning to the Desktop tab later triggers `_maybe_load_desktop()` which calls `setUrl(...)` again, reloading the page. This matches the user observation that clicking Desktop “fully reloads the window/page” and may contribute to the crash if the segfault is triggered by repeated navigations.

## 6. Suggested investigation steps (for the next agent)
- Capture a Python-side traceback on segfault:
  - Run with `AGENTS_RUNNER_FAULTHANDLER=1` and check `~/.midoriai/agents-runner/faulthandler.log`.
- Compare behavior with GPU disabled explicitly:
  - Try setting `QTWEBENGINE_CHROMIUM_FLAGS="--disable-gpu --disable-gpu-compositing --disable-features=Vulkan"` (or equivalent) and see if the crash disappears.
  - If disabling GPU stops the crash, adjust runtime detection to cover the “/dev/dri exists but GBM unusable” case.
- Increase QtWebEngine logging to identify the failing phase:
  - Consider `QT_LOGGING_RULES="qt.webenginecontext.debug=true;qt.webengine*.debug=true"` and Chromium `--enable-logging=stderr --v=1`.
- Validate fontconfig env propagation:
  - Confirm `FONTCONFIG_FILE` is actually set inside the QtWebEngine subprocess environment, and whether the `(null)` error persists.
- Tighten repro:
  - Create a task with headless desktop enabled so `novnc_url` becomes available; then repeatedly switch `Task` ↔ `Desktop` tab and open/close task details from the dashboard.

## 7. Acceptance criteria (clear, testable statements)
- A consistent repro path is documented (or the crash is ruled out as unrelated to Desktop tab).
- The crash is narrowed to one or more of:
  - `QWebEngineView` initialization
  - `QWebEngineView.setUrl(...)` to noVNC URL
  - `QWebEngineView.setUrl("about:blank")` during hide/switch
  - GPU/Vulkan/GBM configuration
  - Fontconfig configuration/propagation
- Concrete, minimal candidate fixes are proposed (but not implemented in this task).

## 8. Related files to inspect when implementing a fix (not now)
- `agents_runner/app.py`
- `agents_runner/ui/pages/task_details.py`
- `agents_runner/ui/main_window.py`
- `agents_runner/ui/main_window_task_events.py`

## 8.1 Mitigation option: out-of-process Desktop viewer
- For isolation from native crashes, run the Desktop (noVNC) viewer in a separate helper process instead of embedding `QWebEngineView` in the main UI.
- Tracking task: `.agents/tasks/wip/qtwebengine-desktop-viewer-out-of-process.md`

## 9. Experiment (startup warm-up navigation)
- Temporary change tested: `agents_runner/app.py:_initialize_qtwebengine()` navigates a hidden `QWebEngineView` to `https://www.google.com` at app startup (warm-up), then `deleteLater()` after ~5s.
- Ran `timeout -k 1s 10s uv run main.py` 5 times:
  - All runs exited `124` (killed by timeout), no `139` observed in this “startup only” scenario.
  - Console output consistently included `GBM is not supported... Fallback to Vulkan...` and repeated JS console messages like `Couldn't fetch defaults.json` / `mandatory.json` and unused preloads under `http://127.0.0.1:<port>/app/images/...`.

## 10. Experiment (looped 10s runs; capturing exit codes)
- Ran `timeout -k 1s 10s env AGENTS_RUNNER_FAULTHANDLER=1 uv run main.py` 15 times:
  - `139` observed: 0
  - `124` (timeout) observed: 13
  - `0` (exited before timeout) observed: 2
- `~/.midoriai/agents-runner/faulthandler.log` remained empty in this run (no segfault captured).

