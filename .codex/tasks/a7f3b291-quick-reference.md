# Git Task Isolation - Quick Reference

## Problem Summary

**Current Issue:** Multiple tasks using the same GitHub repo environment share a single git working directory, causing:
- `.git/index.lock` collisions
- Working tree contamination between tasks
- Branch conflicts
- Potential repository corruption

**Root Cause:** `managed_repo_checkout_path()` returns `~/.midoriai/agents-runner/managed-repos/{env_id}/` - shared across all tasks in that environment.

## Solution Summary

**Core Change:** Make checkout path task-specific:
- **Before:** `managed-repos/{env_id}/`
- **After:** `managed-repos/{env_id}/tasks/{task_id}/`

## Files to Modify

### Critical (Phase 1)
1. **`agents_runner/environments/paths.py`** - Add `task_id` parameter to `managed_repo_checkout_path()`
2. **`agents_runner/ui/main_window_environment.py`** - Pass `task_id` in `_new_task_workspace()`
3. **`agents_runner/ui/main_window_tasks_agent.py`** - Generate `task_id` earlier in flow
4. **`agents_runner/docker/agent_worker.py`** - Verify task-specific workdir usage (may not need changes)

### New Files (Phase 2)
5. **`agents_runner/environments/cleanup.py`** (NEW) - Cleanup utilities for old task directories

### Optional (Phase 3)
6. **`agents_runner/gh/git_lock.py`** (NEW) - File-based locking (probably not needed)

## Implementation Order

```
1. Update paths.py (add task_id param)
   └─> 2. Update main_window_environment.py (pass task_id)
       └─> 3. Update main_window_tasks_agent.py (generate task_id earlier)
           └─> 4. Create cleanup.py (cleanup utilities)
               └─> 5. Integrate cleanup (on task archive)
                   └─> 6. Test concurrent tasks
```

## Testing Quick Checks

**Smoke Test:**
1. Create GitHub environment
2. Start Task A: "Create file A.txt"
3. Start Task B: "Create file B.txt" (while A is running)
4. Verify both complete successfully
5. Check logs for no `.git/index.lock` errors

**Verify Isolation:**
```bash
ls ~/.midoriai/agents-runner/managed-repos/{env_id}/tasks/
# Should see: {task_a_id}/ {task_b_id}/
```

**Verify Cleanup:**
1. Archive completed task
2. Check task directory removed
3. Failed tasks kept (if configured)

## Backward Compatibility

- `managed_repo_checkout_path(env_id)` without `task_id` → returns original path
- Existing single-task workflows → unchanged
- Local workspace mode (`GH_MANAGEMENT_LOCAL`) → unaffected

## Configuration (Future)

Environment variables for tuning:
- `AGENTS_RUNNER_CLEANUP_AGE_DAYS=7` - Auto-cleanup threshold
- `AGENTS_RUNNER_KEEP_FAILED_TASKS=true` - Keep failed task repos for debugging

## Key Design Decisions

1. **Full Clone vs Worktrees**: Chose full clone per task (simpler, more robust)
2. **Cleanup Strategy**: Immediate on archive (default), with age-based fallback
3. **Locking**: Deferred to Phase 3 (probably not needed with isolation)
4. **Disk Usage**: Accept higher disk usage for simplicity (cleanup mitigates)

## Estimated Timeline

- Phase 1 (Core): 2-3 hours
- Phase 2 (Cleanup): 1-2 hours
- Testing: 1-2 hours
- **Total: 4-7 hours** for complete implementation

## Success Criteria

✅ No `.git/index.lock` errors in concurrent scenarios  
✅ Each task has isolated working directory  
✅ Cleanup prevents disk bloat  
✅ 100% backward compatibility  
✅ No performance regressions  

## Open Questions

1. Should failed task repos be auto-cleaned after N days? (Recommend: Yes, 7 days)
2. Should cleanup be immediate or background? (Recommend: Immediate on archive)
3. Need UI indicator for disk usage? (Recommend: Defer to monitoring)

---

**See full plan:** `.codex/tasks/a7f3b291-git-task-isolation.md`
