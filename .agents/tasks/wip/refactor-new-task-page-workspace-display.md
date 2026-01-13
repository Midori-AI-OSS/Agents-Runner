# Refactor New Task Page Workspace Display Logic

## Objective
Replace "mode map" in New Task UI with workspace-type based logic for determining workspace display behavior.

## Files to Modify
- `agents_runner/ui/pages/new_task.py`

## Tasks
1. Find `set_environment_management_modes()` or similar mode map logic
2. Replace with `set_environment_workspace_types()` (or similar)
3. Update workspace line placement logic to check workspace type instead of mode:
   - `WORKSPACE_CLONED`: hide workspace line (repo is cloned)
   - `WORKSPACE_MOUNTED`: show workspace on terminal line (mounted folder)
   - `WORKSPACE_NONE`: show normal workspace line (no workspace)
4. Remove any checks like `mode == "local"`
5. Use workspace type constants consistently

## Acceptance Criteria
- No references to environment "management mode" in New Task page
- Workspace display logic uses `workspace_type`
- Cloned workspace: workspace line hidden
- Mounted workspace: workspace shown on terminal line
- No workspace: normal workspace line shown
- UI correctly reflects workspace type for all environment types
- Manual testing: Create tasks with each workspace type and verify display
- No console errors or UI glitches
