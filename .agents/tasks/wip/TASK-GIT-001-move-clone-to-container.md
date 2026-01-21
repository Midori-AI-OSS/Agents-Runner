# TASK-GIT-001: Move git clone from host script to container preflight

**Priority:** HIGH  
**Dependencies:** None  
**Estimated Complexity:** Medium  
**Blocks:** TASK-LAUNCH-001, TASK-PERMS-001

## Problem
Git clone currently runs in the user's shell instead of being managed by the program. This causes:
- Untracked git operations outside container environment
- Permission issues when container later tries to access `.git`
- Clone output not captured in task logs

## Root Cause
In `agents_runner/ui/main_window_tasks_interactive_docker.py`:
- `gh_clone_snippet` is built (lines 226-243) and added to host shell script (line 799)
- Host script executes clone in user's terminal before attaching to container
- Container has no visibility into clone status or errors

## Acceptance Criteria
1. Git clone executes inside the container, not in host script
2. Clone operations are logged to task logs via `format_log()`
3. Terminal opens only after clone completes successfully
4. Permission errors resolved (container user owns cloned files)
5. Reattach functionality still works (no re-clone on reattach)

## Implementation Notes

### Marker File Specifications
- Clone completion marker: `/tmp/git-clone-complete.marker`
- Clone state tracking: `$HOST_WORKDIR/.agents-clone-state` (contains: task_id, commit_sha, timestamp)

### Preflight Integration
- Add git clone as new preflight step before existing preflights
- Insert after git identity setup, before environment/settings preflights
- Use existing preflight pattern (shell_log_statement for logging)
- Exit preflight with error code if clone fails

### Ownership & Permissions
- Container user (midori-ai) performs clone, automatically owns files
- No additional chown needed (fixes TASK-PERMS-001 simultaneously)
- Host workspace mount remains `:rw` (line 208)

### Reattach Handling
- Check for `.agents-clone-state` file existence on container start
- If exists and task_id matches: skip clone, log "repository already cloned"
- If missing or mismatched: perform clone operation

### File Size Constraint
- NOTE: Target file is 852 lines (exceeds soft max 300, approaching hard max 600)
- Consider extracting git operations to `agents_runner/ui/git_operations.py` if changes push >600 lines

## Files to Modify
- `agents_runner/ui/main_window_tasks_interactive_docker.py` (remove gh_clone_snippet from host script, add to container preflight)
- `agents_runner/ui/shell_templates.py` (may need adjustment to support container-side execution)

## Testing Strategy

### Manual Verification Steps
1. Create a new task with GitHub repo (e.g., `github.com/octocat/Hello-World`)
2. Observe task logs - verify clone happens before "preflight complete" message
3. Verify clone logs appear in task logs with `[container/git][INFO]` prefix
4. Inside container, run: `ls -la $WORKSPACE/.git` - verify owned by `midori-ai` user
5. Exit container, reattach to task - verify logs show "repository already cloned" (no re-clone)
6. Run git commands inside container: `git status`, `git log` - verify no permission errors

### Error Case Testing
7. Test with invalid repo URL - verify error logged, preflight fails gracefully
8. Test with private repo without token - verify auth error logged clearly
9. Test network failure during clone - verify timeout/error handling

### Regression Testing
10. Verify existing tasks without GitHub repos still launch normally
11. Verify reattach to pre-existing containers (before this change) still works
