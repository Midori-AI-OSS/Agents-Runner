# Task 008: Update environment tracking from gh_locked to workspace_type

## Objective
Replace environment list tracking that uses "gh_locked" with workspace_type-based tracking.

## Files to modify
- `agents_runner/ui/main_window_environment.py`
- `agents_runner/ui/pages/new_task.py`

## Changes

### main_window_environment.py

Replace:
```python
def set_gh_locked_envs(...)
```

With:
```python
def set_cloned_envs(...)
```

Update the implementation to filter by `env.workspace_type == WORKSPACE_CLONED` instead of checking a locked boolean.

### new_task.py

Replace checks like:
```python
if env_id in _gh_locked_envs:
```

With:
```python
if env_id in _cloned_envs:
```

Or derive from environment map:
```python
env = env_map.get(env_id)
if env and env.workspace_type == WORKSPACE_CLONED:
```

## Notes
- Rename internal variables: `_gh_locked_envs` → `_cloned_envs`
- Update any helper methods that reference "locked" to use "cloned" terminology
- Ensure environment filtering logic is consistent across UI
