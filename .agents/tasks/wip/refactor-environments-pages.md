# Refactor Environments Pages to Use workspace_type

## Objective
Update environments pages to use `workspace_type` instead of `gh_management_mode`.

## Files to Modify
- `agents_runner/ui/pages/environments.py`
- `agents_runner/ui/pages/environments_actions.py`

## Workspace Type Constants Reference

Import and use these from `agents_runner.environments.model`:
- `WORKSPACE_NONE = "none"` - No workspace
- `WORKSPACE_MOUNTED = "mounted"` - Folder locked/mounted  
- `WORKSPACE_CLONED = "cloned"` - Git repo cloned

Legacy mapping (for reference only):
- `"none"` (gh_management_mode) → `WORKSPACE_NONE`
- `"local"` (gh_management_mode) → `WORKSPACE_MOUNTED`
- `"github"` (gh_management_mode) → `WORKSPACE_CLONED`

## Tasks
1. Find all references to `gh_management_mode` in both files
2. Replace with `workspace_type` equivalents
3. Update any UI display logic that shows mode information
4. Update any form fields or inputs that reference mode
5. Ensure action handlers work with workspace types

## Acceptance Criteria
- No references to `gh_management_mode` in runtime logic
- Environment creation/editing uses `workspace_type`
- Environment list displays correct workspace type information
- All actions (create, edit, delete) work correctly
- Manual testing: Create, edit, and delete environments of each workspace type
- UI displays workspace type information clearly
