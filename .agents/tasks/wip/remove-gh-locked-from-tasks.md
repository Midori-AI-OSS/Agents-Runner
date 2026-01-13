# Remove gh_management_locked Assignments to Tasks

## Objective
Stop copying `gh_management_locked` from environments onto tasks to prevent future regressions.

## Files to Modify
- `agents_runner/ui/main_window_tasks_agent.py`
- `agents_runner/ui/main_window_tasks_interactive.py`
- `agents_runner/ui/main_window_preflight.py`

## Tasks
1. Find all assignments like `task.gh_management_locked = env.gh_management_locked`
2. Remove these assignments
3. Verify that `gh_management_locked` is only used for environment-level locking (if at all)
4. Consider renaming or removing `gh_management_locked` if it's no longer needed

## Acceptance Criteria
- No assignments of `gh_management_locked` to task objects
- Tasks do not carry environment lock state
- Environment lock logic (if needed) remains on Environment model only
- Task creation works correctly without locked field
- Manual testing: Create tasks and verify no locked field is copied
- Task objects have no gh_management_locked attribute set
