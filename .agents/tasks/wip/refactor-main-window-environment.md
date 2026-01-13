# Refactor main_window_environment.py to Use workspace_type

## Objective
Replace `gh_management_mode` usage with `workspace_type` in main window environment logic.

## Files to Modify
- `agents_runner/ui/main_window_environment.py`

## Tasks
1. Find all references to `gh_management_mode` in the file
2. Replace template detection gating to use `workspace_type`
3. Replace management_modes map with workspace_type-based logic
4. Update any conditionals that check mode values
5. Ensure proper handling of:
   - `WORKSPACE_CLONED` (was "clone")
   - `WORKSPACE_MOUNTED` (was "local")
   - `WORKSPACE_NONE` (no workspace)

## Acceptance Criteria
- No references to `gh_management_mode` in runtime logic (read-time migration OK)
- Template detection works correctly based on `workspace_type`
- All mode-based gating uses `workspace_type` constants
- UI displays correct behavior for each workspace type
- Manual testing: Verify template detection for each workspace type
- No console errors or runtime exceptions
