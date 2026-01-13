# Task 004: Add workspace_type migration to task persistence

## Objective
Update task persistence to read old `gh_management_mode` and migrate to `workspace_type`.

## File to modify
`agents_runner/persistence.py`

## Changes

### Task loading/deserialization
Add migration logic when loading saved tasks:

```python
# Prefer new key, fallback to old key
workspace_type = task_data.get("workspace_type")
if not workspace_type and "gh_management_mode" in task_data:
    old_mode = task_data["gh_management_mode"]
    if old_mode == "github":
        workspace_type = "cloned"
    elif old_mode == "local":
        workspace_type = "mounted"
    else:
        workspace_type = "none"

# Fallback: if task has gh_management_locked=True but no mode, default to "none"
# (do NOT assume git based on locked boolean alone)
if not workspace_type and task_data.get("gh_management_locked"):
    workspace_type = "none"

workspace_type = workspace_type or "none"
```

### Task saving/serialization
Write the new `workspace_type` field:

```python
task_data["workspace_type"] = task.workspace_type
```

## Notes
- Do NOT assume `gh_management_locked=True` means git - default to "none" to be safe
- Ensure existing tasks load without errors
- Test with saved task state files
