# Task 003: Wire size check into cleanup ticker + popup with "Don't show again"

**Files:** `agents_runner/ui/main_window_task_recovery.py`, `agents_runner/ui/main_window.py`

**Dependencies:** Task 001 (`get_workspace_tree_size`), Task 002 (`cleanup_by_size`)

## Objective
Wire the size-based cleanup into the existing cleanup ticker, and add a popup that warns when size cleanup runs, with a "Don't show again" persistent option.

## Requirements

### In `main_window_task_recovery.py`

**Imports to add (top of file):**
- `from agents_runner.environments.cleanup import get_workspace_tree_size, cleanup_by_size`
- `from agents_runner.environments.task_workspaces import scratch_drive_status, SCRATCH_TASK_WORKSPACES_ROOT`
- `from pathlib import Path`
- `from PySide6.QtCore import Signal`

1. Define a new `Signal` on `MainWindowTaskRecoveryMixin`: `_size_cleanup_popup_requested = Signal(int)` — emits the count of removed workspaces.

2. In `_run_task_workspace_cleanup()`, after the existing retention-based cleanup (line 155), add a new code block:
   a. Determine the workspace data directory root: `data_dir = os.path.dirname(self._state_path)`. Reuse the `data_dir` variable already used on line 140.
   b. Call `get_workspace_tree_size(Path(data_dir))` to get current total bytes.
   c. Read the threshold from `self._settings_data.get("task_workspace_cleanup_size_threshold_gb", 50)`.
   d. Determine if scratch drive is on tmpfs: call `scratch_drive_status()` and check `is_ram_drive`. Also check if the current `task_workspace_location` setting is `"scratch_drive"`. If both are true, compute dynamic cap:
      - Read `MemTotal` from `/proc/meminfo` (parse the kB value, convert to GB: `kB / (1024*1024)`).
      - `effective_threshold_gb = max(1, min(user_threshold_gb, int(system_ram_gb * 0.5)))`.
      Otherwise `effective_threshold_gb = user_threshold_gb`.
   e. If current size exceeds `effective_threshold_gb * (1024**3)` bytes, call:
      ```
      cleanup_by_size(
          threshold_gb=effective_threshold_gb,
          task_payloads=chain(active_payloads, iter_done_task_payloads(self._state_path)),
          active_task_ids=active_task_ids,
          finalizing_task_ids=finalizing_task_ids,
          data_dir=data_dir,
      )
      ```
      (Note: `active_payloads`, `active_task_ids`, `finalizing_task_ids` are already computed earlier in `_run_task_workspace_cleanup` — reuse them.)
   f. If `removed > 0` AND `not bool(self._settings_data.get("task_workspace_cleanup_size_popup_suppressed", False))`, emit `self._size_cleanup_popup_requested.emit(removed)`.
   g. Log the result via `self.host_log.emit(...)` using `format_log("cleanup", "size", "INFO", ...)`.

3. Per-session dedup: after first popup emission in a session, set a private flag `self._size_cleanup_popup_shown_this_session = True`. Check this flag before emitting so popup only shows once per app session, regardless of ticker frequency.

### In `main_window.py`

1. In the class that mixes in `MainWindowTaskRecoveryMixin`, connect the signal (e.g. in `__init__` or `_setup_signals`):
   ```python
   self._size_cleanup_popup_requested.connect(self._on_size_cleanup_popup)
   ```

2. Add slot method `_on_size_cleanup_popup(self, removed_count: int)`:
   a. Check `self._size_cleanup_popup_shown_this_session` — return early if already shown.
   b. Set `self._size_cleanup_popup_shown_this_session = True`.
   c. Create a `QMessageBox` with:
      - **Icon:** `QMessageBox.Icon.Information`
      - **Title:** "Workspace Size Cleanup"
      - **Text:** f"Task workspaces exceeded the {threshold_gb} GB size limit.\n{removed_count} old workspace(s) were removed."
      - **Informative text:** "Consider using a RAM drive for scratch data to avoid disk limits."
   d. Add a `QCheckBox("Don't show again")` via `msg_box.setCheckBox(checkbox)`.
   e. Add buttons:
      - `QMessageBox.StandardButton.Close` (reject role)
      - Custom button: `msg_box.addButton("Open Settings", QMessageBox.ButtonRole.AcceptRole)`
   f. Execute the dialog. After it closes:
      - If "Don't show again" was checked, set `self._settings_data["task_workspace_cleanup_size_popup_suppressed"] = True` and call `self._schedule_save()`.
      - If "Open Settings" was clicked, open settings and navigate to the Cleanup pane:
        ```python
        self._settings.show()
        self._settings._on_nav_button_clicked("cleanup")
        ```

## Acceptance Criteria
- After retention cleanup, size is checked and size cleanup runs if over threshold.
- Dynamic RAM cap works correctly for scratch drive on tmpfs (capped at 50% of system RAM).
- Popup appears only when workspaces are actually removed by size cleanup.
- "Don't show again" checkbox persists across app restarts via `task_workspace_cleanup_size_popup_suppressed`.
- "Open Settings" button opens settings to the Cleanup pane.
- Popup only shows once per app session regardless of cleanup ticker frequency.
- Popup is suppressed entirely if `task_workspace_cleanup_size_popup_suppressed` is True at startup.

## Notes
- `_run_task_workspace_cleanup` runs in a daemon thread. Qt `Signal.emit()` is thread-safe and uses queued connections for cross-thread delivery.
- For tmpfs detection in the ticker, use `scratch_drive_status()` (already available in `agents_runner.environments`).
- For /proc/meminfo parsing, read the file inline — do not add a new utility module.
- Follow existing Qt patterns and `host_log.emit` formatting in `main_window_task_recovery.py`.
- Use `midori_ai_logger` for logging where appropriate.
