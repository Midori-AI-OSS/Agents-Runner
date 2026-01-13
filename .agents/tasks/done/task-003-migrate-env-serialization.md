# Task 003: Add workspace_type migration to environment serialization

## Objective
Update environment serialization to read old `gh_management_mode` and migrate to `workspace_type`.

## File to modify
`agents_runner/environments/serialize.py`

## Changes

### Read path (deserialization)
Add migration logic when loading environments:

```python
# Prefer new key, fallback to old key
workspace_type = data.get("workspace_type")
if not workspace_type and "gh_management_mode" in data:
    old_mode = data["gh_management_mode"]
    if old_mode == "github":
        workspace_type = "cloned"
    elif old_mode == "local":
        workspace_type = "mounted"
    else:
        workspace_type = "none"
else:
    workspace_type = workspace_type or "none"

# Normalize using the new function
workspace_type = normalize_workspace_type(workspace_type)
```

### Write path (serialization)
Write the new `workspace_type` field:

```python
data["workspace_type"] = env.workspace_type
```

Optionally also write old `gh_management_mode` for backward compatibility (one release cycle):
```python
# Backward compatibility (optional)
if env.workspace_type == "cloned":
    data["gh_management_mode"] = "github"
elif env.workspace_type == "mounted":
    data["gh_management_mode"] = "local"
```

## Notes
- Ensure migration handles missing/unknown values gracefully
- Test with existing environment files to ensure no data loss
