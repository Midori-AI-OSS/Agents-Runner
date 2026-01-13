# Remove gh_management_mode from Environment Model

## Objective
Remove `Environment.gh_management_mode` from the model and eliminate `normalize_gh_management_mode()` usage from all runtime paths.

## Files to Modify
- `agents_runner/environments/model.py`

## Context Notes
- Read-time migration exists in `agents_runner/environments/serialize.py`
- The `normalize_gh_management_mode()` function can remain for deserialization only
- Keep the function if it's still used in deserialization, but remove from runtime paths
- Focus on removing the field from the Environment class definition

## Tasks
1. Remove `gh_management_mode` field from `Environment` class
2. Remove `normalize_gh_management_mode()` function if it exists
3. Keep **read-time** migration only in deserialization code (deserialize old `gh_management_mode` → `workspace_type`)
4. Ensure `workspace_type` is used throughout the model

## Acceptance Criteria
- `Environment.gh_management_mode` attribute no longer exists
- `normalize_gh_management_mode()` is removed or only used during deserialization
- All environment logic uses `workspace_type` instead
- Tests pass (if applicable)
- Manual verification: Environment creation and loading still works
- No runtime errors from missing attribute references
