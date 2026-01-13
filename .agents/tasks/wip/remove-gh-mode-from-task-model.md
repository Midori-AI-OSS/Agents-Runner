# Remove gh_management_mode from Task Model

## Objective
Remove `Task.gh_management_mode` usage for any gating logic. Derive everything from `Task.workspace_type`.

## Files to Check
- `agents_runner/tasks/model.py` (or wherever Task model is defined)
- Any code that references `task.gh_management_mode`

## Tasks
1. Remove `gh_management_mode` field from `Task` class
2. Ensure all task gating uses `Task.workspace_type` 
3. Ensure `Task.requires_git_metadata()` uses `workspace_type` correctly
4. Keep read-time migration for deserialization if needed

## Acceptance Criteria
- `Task.gh_management_mode` attribute no longer exists (or is only used for deserialization)
- All task gating logic uses `Task.workspace_type`
- `requires_git_metadata()` returns correct values based on workspace type
- Tests pass
- Manual verification: Task creation and PR gating work correctly
- No runtime errors from missing attribute references
