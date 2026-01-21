# TASK-PERMS-001: Fix permission handling for git operations

## Problem
Permission denied errors occur on `.git` directory when:
- Clone runs on host (different user) then container tries to access
- Git operations need to work across host/container boundary

Error example:
```
/home/lunamidori/.midoriai/agents-runner/managed-repos/env-de3fef5d/tasks/539ac650a4/.git: Permission denied
[host/clone][ERROR] 'git clone failed (exit 1)'
```

## Root Cause
- Host user (lunamidori) and container user (midori-ai) have different UIDs
- When clone runs on host, files owned by host user
- Container cannot read/write files owned by different user

## Acceptance Criteria
1. Git operations complete without permission errors
2. Both host and container can read/write repository files
3. No security regression (files still protected from other users)
4. Works consistently across different host usernames/UIDs

## Implementation Notes
This task is dependent on TASK-GIT-001. Once clone runs inside container:
- Container user (midori-ai) owns cloned files
- Host workspace mount should be `rw` (already is, line 208)
- May need to ensure container user UID matches host UID for seamless file access
- Alternative: use appropriate mount options (`:Z` for SELinux, etc.)

If UIDs don't match, consider:
- Running container with `--user $(id -u):$(id -g)`
- Using ACLs on mounted directory
- Post-clone chown operation

## Files to Modify
- `agents_runner/ui/main_window_tasks_interactive_docker.py` (docker run args, line 204-218)
- May need changes to mount point configuration

## Verification Steps
1. Create task with GitHub repo
2. Run git operations inside container (commit, branch, etc.)
3. Verify no permission errors
4. Check file ownership: `ls -la <workspace>/.git`
5. Test on different host user account if possible
