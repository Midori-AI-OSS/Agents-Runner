# Task 002: Add workspace_type to Task model

## Objective
Add workspace_type field to the Task model to track environment type per task.

## File to modify
`agents_runner/ui/task_model.py`

## Changes

1. Import workspace type constants from environment model:
   ```python
   from agents_runner.environments.model import WORKSPACE_NONE, WORKSPACE_MOUNTED, WORKSPACE_CLONED
   ```

2. Add new field to `Task` class:
   ```python
   workspace_type: str = WORKSPACE_NONE
   ```

## Notes
- Do NOT remove `gh_management_mode` or `gh_management_locked` fields yet
- This is purely additive to support migration
- The field will be populated during task creation flows in later tasks
