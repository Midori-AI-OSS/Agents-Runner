# Refactor Preflight Logic to Use workspace_type

## Objective
Update preflight checks to use `workspace_type` instead of `gh_mode`/`gh_locked`.

## Files to Modify
- `agents_runner/ui/main_window_preflight.py`

## Context Notes
- `gh_locked` refers to `gh_management_locked` on the Environment model
- This field controls whether environment settings are editable
- Tasks should NOT copy this field (this is covered in a separate task)
- Focus on replacing `gh_mode` references with `workspace_type` checks
- The recreate logic should use `workspace_type` to determine environment behavior

## Tasks
1. Find all references to `gh_mode` and `gh_locked` in preflight logic
2. Replace with `workspace_type` equivalents
3. Update environment recreate logic to use workspace types
4. Remove any copying of `gh_management_locked` to tasks
5. Ensure preflight validation works for all workspace types

## Acceptance Criteria
- No references to `gh_mode` or `gh_management_mode` in runtime logic
- Preflight checks use `workspace_type` correctly
- Environment recreation works for all workspace types
- No `gh_management_locked` copied to tasks
- Manual testing: Run preflight with each workspace type
- Environment recreation succeeds without errors
