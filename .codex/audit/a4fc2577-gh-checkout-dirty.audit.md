# Audit: GH PR Finalize Fails On Dirty Checkout

**ID:** a4fc2577  
**Date:** 2026-01-06  
**Area:** `agents_runner/gh/task_plan.py` (`commit_push_and_pr`)

## Observed Failure

PR finalization can fail with:

```
error: Your local changes to the following files would be overwritten by checkout:
  <file>
Please commit your changes or stash them before you switch branches.
Aborting
```

This happens when `commit_push_and_pr()` runs `git checkout <task-branch>` while the repo has uncommitted changes on a different branch that conflict with the target branch’s version of a file.

## Root Cause

- `commit_push_and_pr()` currently assumes it can always `git checkout <task-branch>` before committing.
- If the agent (or a concurrent process) switched branches during the task, the working tree can be dirty on a non-task branch at finalize time.
- Git refuses to checkout the task branch because it would overwrite local changes.

## Impact

- Automated PR creation fails even though the task produced valid changes.
- Users may need to manually stash/commit/resolve before PR creation proceeds.

## Recommendation

Make branch switching in `commit_push_and_pr()` robust:

1. If already on the requested branch, proceed.
2. If not, and the worktree is dirty:
   - Retry checkout with `--merge` to preserve local changes when possible.
   - If that fails, auto-stash (including untracked), checkout the branch, then apply the stash.
   - If stash apply conflicts, abort with a clear error message indicating manual conflict resolution is required (stash should remain for safety).

This change reduces user-facing “checkout would overwrite” failures without discarding work.

