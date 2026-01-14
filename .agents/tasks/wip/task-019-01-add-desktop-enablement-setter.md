# Task 019-01: Add desktop enablement setter to NewTaskPage

## Parent
task-019-new-task-interactive-desktop-mounted.md

## Problem
NewTaskPage needs to receive desktop enablement information (from both per-environment settings and global force-desktop setting) to determine whether to show the interactive desktop dropdown menu.

## Location
- `agents_runner/ui/pages/new_task.py`

## Changes Required

### Data Structure
- Use `_env_desktop_enabled: dict[str, bool] = {}` instead of a simple boolean
- Store desktop enablement status per environment ID
- Check the dictionary in `_sync_interactive_options()` using current environment ID

### Implementation Sequence
1. Add instance variable: `_env_desktop_enabled: dict[str, bool] = {}`
2. Update `_sync_interactive_options()` to check `self._env_desktop_enabled.get(env_id, False)`
3. REPLACE the `workspace_type == WORKSPACE_CLONED` check (line 427) with desktop enablement check

## Acceptance Criteria
- [ ] NewTaskPage has `_env_desktop_enabled: dict[str, bool]` instance variable initialized to empty dict
- [ ] `_sync_interactive_options()` uses `_env_desktop_enabled.get(env_id, False)` to determine menu visibility
- [ ] Desktop dropdown shows when environment's desktop is enabled (regardless of workspace type)
- [ ] Desktop dropdown hidden when environment's desktop is not enabled
- [ ] Workspace type check is REPLACED (not just removed) with desktop enablement check

## Implementation Notes
- Do not add the setter method yet (that's task 019-02)
- Logic should be: show menu if `env_id` exists AND `_env_desktop_enabled.get(env_id, False)` is True
- REPLACE the `workspace_type == WORKSPACE_CLONED` check (line 427) with desktop enablement check
- The dictionary will be populated by Task 019-02
