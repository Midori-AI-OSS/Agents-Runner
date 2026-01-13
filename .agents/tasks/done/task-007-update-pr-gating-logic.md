# Task 007: Update PR availability checks to use workspace_type

## Objective
Replace all PR gating logic that checks `gh_management_locked` with `workspace_type == "cloned"`.

## Files to modify
- `agents_runner/ui/main_window_task_review.py`
- Any other files that check PR availability

## Changes

Replace pattern:
```python
if task.gh_management_locked:
    # show PR controls
```

With:
```python
if task.workspace_type == WORKSPACE_CLONED:
    # show PR controls
```

Or using the new method:
```python
if task.requires_git_metadata():
    # show PR controls
```

## Specific checks to update

### main_window_task_review.py
Find all PR availability/gating checks and update them to use `workspace_type`.

Common patterns:
- Enabling/disabling PR creation buttons
- Showing/hiding PR UI elements
- Validating PR actions

## Notes
- PR controls should ONLY appear for `workspace_type == "cloned"`
- Mounted/folder environments must NEVER show PR options
- Update any related error messages to say "only available for cloned environments"
