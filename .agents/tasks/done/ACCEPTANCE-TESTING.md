# Acceptance Testing Summary for workspace_type Refactor

## Implementation Complete

The following tasks have been completed:

1. ✅ Task 10: UI labels updated from "locked" to "mounted/cloned" terminology
2. ✅ Task 11: Added workspace_target field with backward compatibility
3. ⏸️ Task 12: Remove gh_management_mode field (deferred - needs full migration)
4. ⏸️ Task 13: Handle gh_management_locked field (deferred - depends on task 12)
5. ✅ Task 14: Update internal docs (none found needing updates)
6. ✅ Task 15: Git context injection updated to use workspace_type
7. ✅ Task 16: Repo root lookup fixed to use workspace_target

## Manual Testing Required

### Test 1: Mounted Environment Behavior
**Setup:** Create a new environment using "Mount local folder" option
- [ ] Verify UI shows "Mount local folder" (not "Lock to local folder")
- [ ] Verify no PR controls visible
- [ ] Verify workspace path shows correctly
- [ ] Create and run a task in this environment
- [ ] Verify folder is mounted correctly (not cloned)
- [ ] If folder contains .git, verify git context is available

### Test 2: Cloned Environment Behavior
**Setup:** Create a new environment using "Clone GitHub repo" option
- [ ] Verify UI shows "Clone GitHub repo" (not "Lock to GitHub repo")
- [ ] Verify base branch selection dropdown appears
- [ ] Create and run a task in this environment
- [ ] Verify repository is cloned per task
- [ ] Verify PR creation options appear
- [ ] Verify git context is available

### Test 3: Backward Compatibility - Environments
**Setup:** Create test files with old gh_management_mode format
```json
{
  "env_id": "test-old-github",
  "name": "Old GitHub Env",
  "gh_management_mode": "github",
  "gh_management_target": "owner/repo"
}
```
```json
{
  "env_id": "test-old-local",
  "name": "Old Local Env",
  "gh_management_mode": "local",
  "gh_management_target": "/path/to/folder"
}
```
- [ ] Verify environments load without errors
- [ ] Verify "github" migrates to workspace_type="cloned"
- [ ] Verify "local" migrates to workspace_type="mounted"
- [ ] Verify workspace_target is populated correctly
- [ ] Verify environments display with correct UI terminology

### Test 4: Backward Compatibility - Tasks
**Setup:** Load existing tasks with old gh_management_mode field
- [ ] Verify tasks load without errors
- [ ] Verify task environment types are correct
- [ ] Verify PR controls appear/hide based on workspace_type

### Test 5: UI Terminology Audit
**Manual review of all UI screens:**
- [ ] New Task page - check labels and tooltips
- [ ] Environments page - check dropdowns and labels
- [ ] Task Details page - check terminology
- [ ] Settings/Preferences - check any environment-related text
- [ ] Error messages - verify they use correct terminology
- [ ] Comments in new_task.py correctly say "mounted folder" not "folder locked"

## Known Limitations

1. **gh_management_mode field**: Still present in model for backward compatibility. Full removal deferred until all code migrated to workspace_type.

2. **gh_management_locked field**: Needs decision on whether to delete or rename. Currently unchanged.

3. **UI variable names**: Internal UI variables like `_gh_management_mode` and `_gh_management_target` still use old naming for backward compatibility.

## Regression Testing Checklist

- [ ] Existing environments continue to work
- [ ] Existing tasks continue to work
- [ ] Environment creation still works
- [ ] Task creation still works
- [ ] Task execution (agent mode) still works
- [ ] Task execution (interactive mode) still works
- [ ] Git context injection still works
- [ ] PR creation still works (if applicable)

## Test Data Location

Test environment and task JSON files can be created in:
- `~/.midoriai/agents-runner/environments/` for environment files
- `~/.midoriai/agents-runner/tasks/` for task files

## Notes

- Manual testing should be performed before merging this branch
- Consider creating automated tests for critical paths in future work
- UI screenshots can be attached to the PR for review
