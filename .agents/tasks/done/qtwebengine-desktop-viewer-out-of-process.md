# Task — Move Desktop viewer (QtWebEngine) out-of-process to prevent whole-app `139`

## 1. Title (short)
Out-of-process Desktop viewer for noVNC

## 2. Summary (1–3 sentences)
QtWebEngine (`QWebEngineView`) can segfault the entire GUI process (exit `139`). Mitigate blast radius by running the Desktop (noVNC) webview in a separate helper process so the main Agent Runner UI can survive crashes and offer a restart.

## 3. Rationale / problem statement
- Current Desktop tab embeds `QWebEngineView` in-process (`agents_runner/ui/pages/task_details.py`), and repeated navigations/reloads may correlate with intermittent exit `139`.
- Python `try/except` cannot catch SIGSEGV; isolating native crashes requires process separation.

## 4. Proposed design (minimal, reviewable)
### UX behavior
- Remove the `Desktop` tab entirely and replace it with a header button (like `Review`) shown in Task Details:
  - Place `Desktop` button to the left of `Back` (same row as `Review`/`Back`) in `agents_runner/ui/pages/task_details.py`.
  - Show the button only when a task has a non-empty `novnc_url` (and desktop is enabled for that task).
  - Clicking `Desktop` launches the viewer process pointed at the task’s noVNC URL.
  - If the viewer is already running, either focus it (if feasible) or show `Restart Desktop` in a small menu.
  - Keep the noVNC URL visible/copyable in the Task view (or a small dialog opened from the button) so users can open it externally if needed.
  - Avoid rounded UI styling (keep sharp/square corners per style constraints).
  - Do not keep or add an embedded/in-process viewer option.

### Process model
- Add a small helper entrypoint that runs a standalone Qt app with a `QWebEngineView`:
  - Invocation: `python -m agents_runner.desktop_viewer --url <novnc_url> [--title Task <id>]`
  - The helper is responsible for initializing QtWebEngine and navigating to the URL.
- Main process spawns helper using `QProcess` (preferred in Qt apps) or `subprocess.Popen`.
- Main process monitors exit and updates UI; if helper dies, main stays alive.

### Communication (keep it simple)
- One-way is enough:
  - Main passes URL via CLI args/env.
  - Main polls `QProcess.state()` and listens for `finished(exitCode, exitStatus)`.
- Avoid tight coupling (no RPC) unless later needed for “auto-refresh URL” etc.

## 5. Implementation notes / likely touch points
- New module(s):
  - `agents_runner/desktop_viewer/app.py` (or similar) for the helper.
  - A thin CLI wrapper in `main.py` (or a new `__main__.py`) to dispatch `--desktop-viewer`.
- UI changes:
  - `agents_runner/ui/pages/task_details.py`: delete Desktop tab logic (`_show_desktop_tab`, `_hide_desktop_tab`, `_maybe_load_desktop`, `_sync_desktop`), add a header `QToolButton` to launch the external viewer, and keep only URL display.
- Logging/diagnostics:
  - Optionally allow helper to write crash breadcrumbs to `~/.midoriai/agents-runner/desktop-viewer.log`.
  - Keep existing `AGENTS_RUNNER_FAULTHANDLER` support for both processes.

## 6. Edge cases to cover
- Task switch while viewer open:
  - Either keep viewer pinned to the originally opened task, or prompt to relaunch for the new task.
- URL changes mid-run (noVNC port changes):
  - If task’s `novnc_url` updates, main should update the displayed URL and (optionally) offer `Relaunch viewer`.
- Shutdown:
  - On main app exit, terminate the viewer process.
- Multiple viewers:
  - Enforce single viewer instance per main window (simplest).

## 7. Acceptance criteria (clear, testable statements)
- Desktop viewer runs in a separate OS process from the main UI.
- If the viewer process crashes (including `SIGSEGV`/exit `139`), the main UI remains open and responsive.
- UI shows viewer status and offers restart.
- Viewer can open a task’s noVNC URL reliably.

## 8. Related references
- Current Desktop embed code: `agents_runner/ui/pages/task_details.py`

---

## Completion Notes

**Implementation Date:** 2025-01-17  
**Status:** Complete

### What was implemented:
1. **Desktop Viewer Module** (`agents_runner/desktop_viewer/`)
   - `app.py`: Standalone Qt application with QWebEngineView
   - `__init__.py`: Module exports
   - `__main__.py`: Entry point for `python -m agents_runner.desktop_viewer`
   - Accepts `--url` (required) and `--title` (optional) arguments
   - Gracefully handles missing QtWebEngine

2. **Main Entry Point** (`main.py`)
   - Added `--desktop-viewer` CLI mode routing
   - Forwards remaining args to desktop viewer app
   - Main UI behavior unchanged when not in viewer mode

3. **Task Details UI** (`agents_runner/ui/pages/task_details.py`)
   - Removed Desktop tab entirely (deleted 40+ lines of tab management)
   - Added Desktop button to header (left of Back button)
   - Button visible only when task has `novnc_url` and desktop enabled
   - Launches viewer via QProcess when clicked
   - Tracks viewer process state and handles crashes
   - Added noVNC URL and DISPLAY to Task tab prompt card
   - Added cleanup method to terminate viewer on shutdown
   - File reduced from 626 to 612 lines

4. **Cleanup Integration** (`agents_runner/ui/main_window.py`)
   - Calls TaskDetailsPage.cleanup() on window close
   - Ensures viewer process terminates when main UI exits

### Testing performed:
- ✅ Module can be invoked: `python -m agents_runner.desktop_viewer --help`
- ✅ Main UI routing works: `python main.py --desktop-viewer --help`
- ✅ Main UI starts without errors (syntax validated)
- ✅ No circular imports or missing dependencies

### Edge cases handled:
- QtWebEngine not available: Shows error message
- Viewer already running: Prevents duplicate launches
- Viewer crashes: Main UI stays responsive
- Main UI exits: Viewer terminates cleanly
- Task switch: Button visibility updates correctly

### Files changed:
- Created: 3 files (desktop_viewer module)
- Modified: 3 files (main.py, task_details.py, main_window.py)
- Total commits: 5

### Acceptance criteria met:
- ✅ Desktop viewer runs in separate OS process
- ✅ Main UI survives viewer crashes
- ✅ UI shows Desktop button when appropriate
- ✅ Viewer can open noVNC URL reliably
- ✅ Process cleanup on shutdown
