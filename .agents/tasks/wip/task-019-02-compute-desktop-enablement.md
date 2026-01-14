# Task 019-02: Compute and pass desktop enablement to NewTaskPage

## Parent
task-019-new-task-interactive-desktop-mounted.md

## Problem
MainWindow needs to compute whether desktop is enabled (from per-environment `headless_desktop_enabled` OR global `settings_data["headless_desktop_enabled"]`) and pass this to NewTaskPage.

## Prerequisites
- Task 019-01 must be completed (NewTaskPage ready to receive desktop enablement map)

## Desktop Enablement Logic
Desktop is enabled for an environment if EITHER:
- Per-environment setting: `env.headless_desktop_enabled == True`, OR
- Global setting: `self._settings_data.get("headless_desktop_enabled", False) == True`

Logic: `env.headless_desktop_enabled or self._settings_data.get("headless_desktop_enabled", False)`

## Location
- `agents_runner/ui/main_window_environment.py`

## Changes Required
1. In `_populate_environment_pickers()`:
   - Compute desktop enablement per environment: `env.headless_desktop_enabled OR self._settings_data.get("headless_desktop_enabled", False)`
   - Build dict `desktop_enabled_map: dict[str, bool]` mapping env_id to computed desktop enablement
   - Call `self._new_task.set_environment_desktop_enabled(desktop_enabled_map)` (new method)

2. Create `set_environment_desktop_enabled()` method in NewTaskPage:
   - Accept `desktop_enabled: dict[str, bool]`
   - Store as `_env_desktop_enabled`
   - Call `_sync_interactive_options()` to refresh menu visibility

3. Update NewTaskPage `_sync_interactive_options()`:
   - Use `self._env_desktop_enabled.get(env_id, False)` to determine desktop enablement for current environment

## Acceptance Criteria
- [ ] `_populate_environment_pickers()` computes desktop enabled per environment (env setting OR global setting)
- [ ] NewTaskPage has `set_environment_desktop_enabled(desktop_enabled: dict[str, bool])` method
- [ ] NewTaskPage stores desktop enablement map in `_env_desktop_enabled` instance variable
- [ ] `_sync_interactive_options()` checks `_env_desktop_enabled` for current environment
- [ ] Desktop menu shows for mounted envs when either env or global desktop enabled
- [ ] Desktop menu shows for cloned envs when either env or global desktop enabled
- [ ] Desktop menu hidden when neither env nor global desktop enabled

## Implementation Notes
- Desktop enablement logic: `env.headless_desktop_enabled OR settings["headless_desktop_enabled"]`
- Must update both environment types (mounted and cloned) equally
- Call from same location that calls `set_environment_workspace_types()` and `set_environment_stains()`
