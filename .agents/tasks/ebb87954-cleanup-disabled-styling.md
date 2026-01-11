# Task: Clean up auto merge control disabled state styling

## Objective
Remove custom disabled styling from the auto merge checkbox and ensure the control appears as a normal enabled checkbox when visible (only in git-locked environments).

## Context
The current implementation has custom disabled styling (`QCheckBox:disabled { color: #EDEFF5; }`) on lines 221-223. Since the control will only be visible when it's meant to be used (git-locked environments with GitHub context enabled), it should appear as a normal enabled control. When it cannot be used, it should be hidden entirely (not disabled).

## Files to Modify
- `agents_runner/ui/pages/environments.py`

## Implementation Steps

1. Remove the custom stylesheet from `self._merge_agent_auto_start_enabled` (lines 221-223)
2. Remove or update the enabled/disabled logic at line 635
3. Ensure the checkbox is always enabled when visible
4. The control should be hidden entirely when conditions are not met (see task fdea4f90)
5. Remove any gray/disabled-looking text styling

## Current Code to Remove (Lines 221-223):

```python
self._merge_agent_auto_start_enabled.setStyleSheet(
    "QCheckBox:disabled { color: #EDEFF5; }"
)
```

## Current Enabled Logic (Line 635):

```python
self._merge_agent_auto_start_enabled.setEnabled(merge_supported)
```

This line should be removed because:
- When visible (git-locked + GitHub context enabled), the checkbox should be enabled
- When not usable, the entire control should be hidden (not disabled)

## Logic Context (Lines 624-635):

```python
merge_supported = bool(
    is_github_env
    and bool(getattr(env, "gh_management_locked", False))
    and bool(getattr(env, "gh_context_enabled", False))
)
is_git_locked = bool(getattr(env, "gh_management_locked", False))
self._merge_agent_label.setVisible(is_git_locked)
self._merge_agent_row.setVisible(is_git_locked)
self._merge_agent_auto_start_enabled.setChecked(
    bool(getattr(env, "merge_agent_auto_start_enabled", False))
)
self._merge_agent_auto_start_enabled.setEnabled(merge_supported)  # Remove this
```

## Decision Tree for Proper Behavior

The checkbox should be:
1. **Visible + Enabled** when:
   - `gh_management_mode == GH_MANAGEMENT_GITHUB` (is_github_env)
   - `gh_management_locked == True`
   - `gh_context_enabled == True`
   
2. **Hidden** (not disabled) when any of the above conditions are false

## Expected Behavior After Fix

- Line 635 removed entirely (no setEnabled call)
- Lines 221-223 removed (no custom disabled styling)
- Checkbox always appears enabled when visible
- Visibility controlled by task fdea4f90 logic

## Code to Remove
```python
self._merge_agent_auto_start_enabled.setStyleSheet(
    "QCheckBox:disabled { color: #EDEFF5; }"
)
```

## Logic to Update
- Line 635: Remove `setEnabled(merge_supported)` call entirely
- The control should be enabled whenever it's visible
- Hide the control entirely when `merge_supported` is False (handled by task fdea4f90)

## Implementation Order Note

**Important:** This task should be completed AFTER task fdea4f90 (hide-automerge-folder-locked) because:
- Task fdea4f90 updates visibility logic to hide the control when not usable
- Once visibility is correct, the setEnabled logic becomes unnecessary
- This prevents the control from ever appearing in a disabled state

## Additional Context

The `merge_supported` variable calculation (lines 624-628) can remain for tooltip logic, but should not control the enabled state:
```python
merge_supported = bool(
    is_github_env
    and bool(getattr(env, "gh_management_locked", False))
    and bool(getattr(env, "gh_context_enabled", False))
)
```

Initial enabled state is set to False at line 220, which can also be removed or changed to True.

## Acceptance Criteria
- [ ] No custom disabled styling on the auto merge checkbox
- [ ] Checkbox appears with normal text color when visible
- [ ] Checkbox is interactive (enabled) when shown in git-locked environments
- [ ] No gray or disabled-looking text for this control
- [ ] Control is hidden (not disabled) when conditions are not met

## Testing
1. Open a git-locked environment with GitHub context enabled
2. Verify the checkbox has normal black text (not gray)
3. Verify the checkbox is clickable and interactive
4. Open a folder-locked environment
5. Verify the control is completely hidden (not present as disabled)
