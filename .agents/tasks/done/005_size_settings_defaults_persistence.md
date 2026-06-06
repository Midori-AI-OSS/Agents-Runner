# Task 005: Add new settings defaults + persistence for size cleanup settings

**Files:** `agents_runner/ui/main_window.py`, `agents_runner/ui/main_window_persistence.py`, `agents_runner/ui/main_window_settings.py`

**Also touches:** `agents_runner/environments/task_workspaces.py` (normalize function)

**Dependencies:** None strict, but the settings keys defined here are consumed by Tasks 003 and 004.

## Objective
Add default values for the two new settings keys and ensure they survive the save/load round-trip.

## New settings keys
- `task_workspace_cleanup_size_threshold_gb` (int, default: 50)
- `task_workspace_cleanup_size_popup_suppressed` (bool, default: False)

## Requirements

### In `main_window.py` (~line 91-132)
1. Add the two new defaults to the `_settings_data` init dict:
   ```python
   "task_workspace_cleanup_size_threshold_gb": 50,
   "task_workspace_cleanup_size_popup_suppressed": False,
   ```
   Add them near the existing cleanup setting defaults (lines 129-131).

### In `main_window_persistence.py` (`_load_state` method)
2. Add `setdefault` calls for the two new keys, following the existing pattern (lines 180-213):
   ```python
   self._settings_data.setdefault("task_workspace_cleanup_size_threshold_gb", 50)
   self._settings_data.setdefault("task_workspace_cleanup_size_popup_suppressed", False)
   ```
   Note: `_save_state` (line 128) already saves `self._settings_data` wholesale via `payload["settings"] = settings_payload`, so new keys are automatically persisted — no changes needed there.

### In `main_window_settings.py` (`_apply_settings` method)
3. Add normalization for the new keys, following existing cleanup setting patterns:
   ```python
   try:
       merged["task_workspace_cleanup_size_threshold_gb"] = max(1, min(1000, int(merged.get("task_workspace_cleanup_size_threshold_gb", 50))))
   except Exception:
       merged["task_workspace_cleanup_size_threshold_gb"] = 50
   merged["task_workspace_cleanup_size_popup_suppressed"] = bool(merged.get("task_workspace_cleanup_size_popup_suppressed", False))
   ```

### In `agents_runner/environments/task_workspaces.py` (`normalize_task_workspace_settings`)
4. Add normalization for `task_workspace_cleanup_size_threshold_gb` to keep this consistent with the other cleanup settings already normalized there (lines 64-85):
   ```python
   normalized["task_workspace_cleanup_size_threshold_gb"] = clamp_int(
       normalized.get("task_workspace_cleanup_size_threshold_gb"),
       minimum=1,
       maximum=1000,
       default=50,
   )
   ```

## Acceptance Criteria
- New keys appear with correct defaults on a fresh config (no pre-existing settings file).
- Values changed via the settings UI survive app restart.
- Values manually edited in `config.toml` are loaded correctly.
- Normalization clamps out-of-range values (threshold < 1 → 1, > 1000 → 1000; popup_suppressed is coerced to bool).
- Existing settings keys are unaffected.
- `task_workspace_cleanup_size_popup_suppressed` set to True persists across restarts (suppresses the popup permanently until user resets).

## Notes
- Follow existing code conventions in each file.
- Do not introduce a new settings framework; extend the existing dict-based pattern.
- `_save_state` already persists `_settings_data` wholesale — no explicit key list is needed for persistence.
- Use `midori_ai_logger` for any logging if needed.
