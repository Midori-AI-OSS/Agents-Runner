# Task: Hide auto merge controls for folder-locked environments

## Objective
Modify the environment settings page to completely hide the auto merge pull request control when the environment is folder-locked. The control must be removed from the UI entirely, not just disabled.

## Context
Currently, the auto merge control visibility is tied to `gh_management_locked` flag, but it should not appear for folder-locked environments at all. It should only appear for git-locked (GitHub-managed) environments.

## Files to Modify
- `agents_runner/ui/pages/environments.py`

## Implementation Steps

1. Locate the visibility logic for the merge agent controls (around lines 629-631)
2. Add a check to ensure the environment is GitHub-managed before showing controls
3. Update the visibility condition to:
   - Check if `gh_management_mode` is `GH_MANAGEMENT_GITHUB`
   - Check if `gh_management_locked` is `True`
   - Both must be true to show the controls
4. Hide all three components when conditions are not met:
   - `self._merge_agent_label`
   - `self._merge_agent_row`
   - `self._merge_agent_auto_start_info`

## Current Code (Lines 629-631)

```python
is_git_locked = bool(getattr(env, "gh_management_locked", False))
self._merge_agent_label.setVisible(is_git_locked)
self._merge_agent_row.setVisible(is_git_locked)
```

## Expected Code After Fix

```python
is_github_env = env.gh_management_mode == GH_MANAGEMENT_GITHUB
is_git_locked = bool(getattr(env, "gh_management_locked", False))
show_merge_controls = is_github_env and is_git_locked
self._merge_agent_label.setVisible(show_merge_controls)
self._merge_agent_row.setVisible(show_merge_controls)
```

## Environment Attributes Reference

The Environment dataclass (in `agents_runner/environments/model.py`, line 69-95) has:
- `gh_management_mode: str` (line 85) - Can be GH_MANAGEMENT_NONE, GH_MANAGEMENT_LOCAL, or GH_MANAGEMENT_GITHUB
- `gh_management_locked: bool` (line 87) - True when locked to a specific repo/folder
- `gh_context_enabled: bool` (line 90) - True when GitHub context is enabled

Constants are imported at top of file (line 27-29):
```python
from agents_runner.environments import GH_MANAGEMENT_GITHUB
from agents_runner.environments import GH_MANAGEMENT_LOCAL
from agents_runner.environments import GH_MANAGEMENT_NONE
```

## Expected Behavior Table

| Environment Type | gh_management_mode | gh_management_locked | Should Show Controls? |
|------------------|-------------------|---------------------|---------------------|
| Folder-locked | GH_MANAGEMENT_LOCAL | True | NO |
| Git-locked | GH_MANAGEMENT_GITHUB | True | YES |
| Unlocked | GH_MANAGEMENT_NONE | False | NO |

## Acceptance Criteria
- [ ] Folder-locked environments do not show the "Merge agent" label
- [ ] Folder-locked environments do not show the "Auto merge pull request" checkbox
- [ ] Folder-locked environments do not show any tooltip icon
- [ ] Git-locked environments still show the control properly
- [ ] No regression in other environment types

## Testing
1. Create/open a folder-locked environment
   - Verify: `gh_management_mode == "local"` and `gh_management_locked == True`
2. Verify no merge agent controls are visible
3. Create/open a git-locked environment
   - Verify: `gh_management_mode == "github"` and `gh_management_locked == True`
4. Verify merge agent controls are visible
5. Test environment switching to ensure correct visibility updates

## Additional Notes
- The icon widget (`self._merge_agent_auto_start_info`) should also respect this visibility logic
- There's cleanup logic at lines 553-558 that resets all widgets when clearing environment
- Initial visibility is set to False at lines 270-271 during widget initialization
