# Refactor Agent Task Creation to Use workspace_type

## Objective
Update agent task creation to use `workspace_type` instead of `gh_management_mode`.

## Files to Modify
- `agents_runner/ui/main_window_tasks_agent.py`

## Tasks
1. Find all assignments like `task.gh_management_mode = ...`
2. Replace with `task.workspace_type = ...` using appropriate constants
3. Remove any logic that copies `gh_management_mode` from environment to task
4. Ensure workspace type is properly inherited from environment when creating tasks

## Acceptance Criteria
- No assignments to `task.gh_management_mode`
- Task creation properly sets `task.workspace_type`
- Agent tasks have correct workspace type based on their environment
- Task behavior matches environment workspace type
- Manual testing: Create agent task in each workspace type environment
- Verify task has correct workspace_type attribute
