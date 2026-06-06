# Task 004: Add size threshold spinbox + dynamic RAM cap to settings UI

**File:** `agents_runner/ui/pages/settings_form.py`

**Also touches:** `agents_runner/ui/pages/settings.py` (autosave wiring)

**Dependencies:** None strict (UI-only), but the setting key it reads/writes is consumed by Task 003 and persisted by Task 005.

## Objective
Add a size threshold spinbox to the Cleanup settings pane, and show a dynamic calculated RAM cap when the scratch drive is on tmpfs.

## Requirements

### In `agents_runner/ui/pages/settings_form.py`

1. In `_build_controls()`, add a new `QSpinBox`:
   ```python
   self._task_workspace_cleanup_size_threshold_gb = QSpinBox()
   self._task_workspace_cleanup_size_threshold_gb.setRange(1, 1000)
   self._task_workspace_cleanup_size_threshold_gb.setSuffix(" GB")
   self._task_workspace_cleanup_size_threshold_gb.setValue(50)
   ```
   Add it to `self._task_workspace_cleanup_controls` list (line 363) so it gets disabled when scratch drive is on RAM drive.

2. Add a dynamic RAM cap label:
   ```python
   self._task_workspace_cleanup_size_ram_cap_label = QLabel("")
   self._task_workspace_cleanup_size_ram_cap_label.setObjectName("SettingsPaneSubtitle")
   self._task_workspace_cleanup_size_ram_cap_label.setWordWrap(True)
   self._task_workspace_cleanup_size_ram_cap_label.setVisible(False)
   ```

3. In `_build_pages()`, add new rows to the cleanup grid (after existing row 2 — "Wait between scans"):
   - Row 3: Label "Workspace size limit" (col 0), spinbox (col 1)
   - Row 4: The RAM cap label (span both columns, or col 1 with col 0 empty)

4. In `set_settings()`, read and apply:
   ```python
   self._task_workspace_cleanup_size_threshold_gb.setValue(
       self._clamp_spin_value(
           settings.get("task_workspace_cleanup_size_threshold_gb"),
           minimum=1, maximum=1000, default=50,
       )
   )
   ```

5. In `get_settings()`, add:
   ```python
   "task_workspace_cleanup_size_threshold_gb": int(self._task_workspace_cleanup_size_threshold_gb.value()),
   ```

6. In `_apply_task_workspace_status()`, after updating the scratch drive status text, add logic to update the RAM cap label:
   - If `scratch_selected` is True and `status.is_ram_drive` is True:
     - Read system RAM via `/proc/meminfo` (`MemTotal`, kB → GB: `kB / 1048576.0`).
     - Compute `effective_cap_gb = max(1, min(spinbox_value, int(system_ram_gb * 0.5)))`.
     - Set label text: `f"Effective cap: {effective_cap_gb} GB (50% of system RAM)"`.
     - Show the label.
   - Otherwise: hide the label and set text to `""`.

7. In `_set_workspace_status_checking()`, hide the RAM cap label when checking is True (add it to the visibility reset logic around line 1600).

### In `agents_runner/ui/pages/settings.py`

8. Wire the spinbox `valueChanged` to autosave (follow pattern of other cleanup spinboxes at line 187-189):
   ```python
   self._task_workspace_cleanup_size_threshold_gb.valueChanged.connect(self._queue_debounced_autosave)
   ```

## Acceptance Criteria
- Spinbox appears in Cleanup pane with range 1-1000, suffix " GB", default 50.
- Value is read from settings on dialog open, and written to settings on dialog accept (via `get_settings()`).
- Dynamic RAM cap label appears when scratch drive is on tmpfs and disappears otherwise.
- Dynamic cap text updates when scratch drive field changes (via `_apply_task_workspace_status`).
- Spinbox is disabled when scratch drive is on RAM drive (via `_task_workspace_cleanup_controls`).
- Label/number formatting matches existing settings form style (use `#SettingsPaneSubtitle`).

## Notes
- Follow existing widget creation and layout patterns in `settings_form.py` (use `add_grid_row`, `configure_form_grid`).
- No `psutil` — it is not a project dependency. Use `/proc/meminfo` for system RAM and rely on existing `scratch_drive_status()` for tmpfs detection.
- The "Don't show again" checkbox for the popup is NOT in this task — it is a runtime popup concern handled in Task 003, persisted via Task 005.
- Existing `ScratchDriveStatus.is_ram_drive` (from `is_tmp_ram_drive()` in `task_workspaces.py`) already provides tmpfs detection.
