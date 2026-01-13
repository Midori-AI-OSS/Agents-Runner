# Task 006: Add Task.requires_git_metadata() method using workspace_type

## Objective
Create a new method on Task that correctly identifies when git metadata is required.

## File to modify
`agents_runner/ui/task_model.py`

## Changes

Add new method to `Task` class:

```python
def requires_git_metadata(self) -> bool:
    """
    Returns True if this task requires git metadata (PR creation, git context, etc.).
    Only cloned workspace environments require git metadata.
    """
    return self.workspace_type == WORKSPACE_CLONED
```

## Notes
- This replaces any existing logic that checks `gh_management_locked`
- Do NOT modify existing `gh_management_locked` checks yet - that comes later
- This method will be used in subsequent refactoring tasks
