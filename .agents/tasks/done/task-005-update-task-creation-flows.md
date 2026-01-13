# Task 005: Update task creation to set workspace_type from environment

## Objective
Update all task creation flows to populate `task.workspace_type` from `env.workspace_type`.

## Files to modify
- `agents_runner/ui/main_window_tasks_agent.py`
- `agents_runner/ui/main_window_tasks_interactive.py`
- `agents_runner/ui/main_window_preflight.py`

## Changes

In each task creation flow, replace:
```python
task.gh_management_locked = env.gh_management_locked
```

With:
```python
task.workspace_type = env.workspace_type
```

## Specific locations to update

### main_window_tasks_agent.py
Find where task is created/configured and add:
```python
task.workspace_type = env.workspace_type
```

### main_window_tasks_interactive.py
Find where task is created/configured and add:
```python
task.workspace_type = env.workspace_type
```

### main_window_preflight.py
Find where task is configured and add:
```python
task.workspace_type = env.workspace_type
```

## Notes
- Keep the old field assignments temporarily for safety
- Do NOT remove `gh_management_locked` assignments yet
- Focus on adding the new field population only
