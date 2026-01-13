# Task 009: Update git configuration gating to use workspace_type

## Objective
Ensure git repository configuration only happens for cloned environments.

## Files to modify
- `agents_runner/ui/main_window_tasks_agent.py`
- `agents_runner/ui/main_window_tasks_interactive.py`
- `agents_runner/ui/main_window_preflight.py`

## Changes

Find any code that configures `gh_repo` or git-related settings.

Replace pattern:
```python
if env.gh_management_locked:
    # configure gh_repo
```

With:
```python
if env.workspace_type == WORKSPACE_CLONED:
    # configure gh_repo
```

## Specific areas to check

- Git repository URL configuration
- Git context injection setup
- Base branch selection
- Any git-specific runner configuration

## Notes
- Git configuration should ONLY happen when `workspace_type == "cloned"`
- Mounted environments may optionally detect git for read-only context, but should not use git-specific configuration
