# Task 001: Add workspace_type constants and normalize function

## Objective
Add new workspace type constants and normalization function to the Environment model.

## File to modify
`agents_runner/environments/model.py`

## Changes

1. Add new constants (near existing `GH_MANAGEMENT_*` constants):
   ```python
   WORKSPACE_NONE = "none"
   WORKSPACE_MOUNTED = "mounted"
   WORKSPACE_CLONED = "cloned"
   ```

2. Add new normalization function (similar to existing `normalize_gh_management_mode`):
   ```python
   def normalize_workspace_type(value: str) -> str:
       """Normalize workspace type to canonical values."""
       if not value or value == "none":
           return WORKSPACE_NONE
       if value in ("github", "git", "repo", "cloned"):
           return WORKSPACE_CLONED
       if value in ("local", "folder", "mounted"):
           return WORKSPACE_MOUNTED
       return WORKSPACE_NONE
   ```

3. Add new field to `Environment` class:
   ```python
   workspace_type: str = WORKSPACE_NONE
   ```

## Notes
- Do NOT remove old `gh_management_mode` fields yet - they will coexist temporarily
- Keep implementation focused on adding new fields only
