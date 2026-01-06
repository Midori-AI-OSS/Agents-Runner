# Git Task Isolation - Implementation Summary

## 📋 Quick Reference

**Problem:** Multiple concurrent tasks share git workspace → locks, conflicts, corruption  
**Solution:** Isolate each task to `managed-repos/{env_id}/tasks/{task_id}/`  
**Effort:** 4-6 hours  
**Risk:** Low (backward compatible, isolated changes)

## 📁 Task Files Created

```
.codex/tasks/
├── a7f3b291-git-task-isolation.md    ← Full detailed plan (18KB)
├── a7f3b291-quick-reference.md       ← Quick reference (3.6KB)
└── a7f3b291-architecture.md          ← Architecture diagrams (8.6KB)
```

## 🎯 Implementation Priorities

### P1 - Critical (Must Do)
1. **agents_runner/environments/paths.py**
   - Add `task_id` param to `managed_repo_checkout_path()`
   - Add `_safe_task_id()` helper

2. **agents_runner/ui/main_window_tasks_agent.py**
   - Generate `task_id` earlier in `_start_task_from_ui()`
   - Pass `task_id` to `_new_task_workspace()`

3. **agents_runner/ui/main_window_environment.py**
   - Update `_new_task_workspace()` signature
   - Pass `task_id` to `managed_repo_checkout_path()`

### P2 - High (Should Do)
4. **agents_runner/environments/cleanup.py** (NEW)
   - Implement `cleanup_old_task_repos()`
   - Implement `cleanup_on_task_completion()`

5. **agents_runner/ui/main_window_tasks_agent.py**
   - Integrate cleanup in `_clean_old_tasks()`

### P3 - Optional (Nice to Have)
6. **agents_runner/gh/git_lock.py** (NEW)
   - File-based locking (probably not needed)

## 🔧 Code Changes Summary

### Change 1: paths.py
```python
def managed_repo_checkout_path(
    env_id: str, 
    data_dir: str | None = None,
    task_id: str | None = None  # ← NEW
) -> str:
    base = os.path.join(managed_repos_dir(data_dir), _safe_env_id(env_id))
    if task_id:
        return os.path.join(base, "tasks", _safe_task_id(task_id))  # ← NEW
    return base  # ← Backward compatible
```

### Change 2: main_window_tasks_agent.py
```python
def _start_task_from_ui(self, prompt, host_codex, env_id, base_branch):
    task_id = uuid4().hex[:10]  # ← Generate EARLY
    # ...
    effective_workdir, ready, message = self._new_task_workspace(
        env, 
        task_id=task_id  # ← Pass task_id
    )
```

### Change 3: main_window_environment.py
```python
def _new_task_workspace(
    self, 
    env: Environment | None,
    task_id: str | None = None  # ← NEW param
) -> tuple[str, bool, str]:
    # ...
    if gh_mode == GH_MANAGEMENT_GITHUB:
        path = managed_repo_checkout_path(
            env.env_id,
            data_dir=os.path.dirname(self._state_path),
            task_id=task_id  # ← Pass through
        )
```

## ✅ Testing Checklist

### Smoke Test (5 minutes)
```bash
# 1. Start two concurrent tasks
Task A: "Create file A.txt"
Task B: "Create file B.txt"

# 2. Verify isolation
ls ~/.midoriai/agents-runner/managed-repos/{env_id}/tasks/
# Should see: {task_a_id}/ {task_b_id}/

# 3. Check logs
grep "index.lock" task_logs.txt
# Should be empty (no lock errors)
```

### Full Test Suite (30 minutes)
- [ ] Concurrent task isolation (no conflicts)
- [ ] Unique checkout directories verified
- [ ] Backward compatibility (local mode)
- [ ] Cleanup removes task dirs
- [ ] Branch management (unique branches)
- [ ] PR creation (correct branches)

## 📊 Expected Outcomes

**Before Implementation:**
```
Concurrent tasks → Lock collisions → Task failures
Disk usage: 100 MB per environment
```

**After Implementation:**
```
Concurrent tasks → Isolated dirs → All tasks succeed ✅
Disk usage: 100 MB per active task (cleaned after completion)
```

## 🚨 Potential Issues & Solutions

| Issue | Solution |
|-------|----------|
| Disk space | Aggressive cleanup (7 day default) |
| Slower clones | Accept tradeoff (correctness > speed) |
| Old tasks linger | Auto-cleanup + manual cleanup button |
| Backward compat broken | Extensive testing, gradual rollout |

## 📈 Rollout Plan

1. **Local Testing** (Day 1)
   - Implement P1 changes
   - Test with 2-3 concurrent tasks
   - Verify no regressions

2. **Cleanup Implementation** (Day 1-2)
   - Implement P2 changes
   - Test cleanup behavior
   - Tune thresholds

3. **Beta Testing** (Day 2-3)
   - Deploy to test users
   - Monitor disk usage
   - Collect feedback

4. **Production** (Day 3+)
   - Deploy to all users
   - Monitor metrics
   - Iterate on cleanup policy

## 🎓 Key Learnings

1. **Isolation > Optimization**: Full clones are simpler than worktrees
2. **Cleanup is Critical**: Without it, disk usage explodes
3. **Backward Compatibility**: Optional param makes migration safe
4. **Testing Matters**: Concurrent scenarios need explicit testing

## 📚 Documentation Links

- **Full Plan:** `.codex/tasks/a7f3b291-git-task-isolation.md`
- **Quick Ref:** `.codex/tasks/a7f3b291-quick-reference.md`
- **Architecture:** `.codex/tasks/a7f3b291-architecture.md`

## 🤝 Handoff to Coder

**Ready for pickup!** 

1. Read `.codex/tasks/a7f3b291-git-task-isolation.md` for full details
2. Start with Phase 1 (Critical Path)
3. Test after each phase
4. Integrate cleanup (Phase 2) before considering complete
5. Phase 3 (locking) can be deferred

**Questions?** Refer to "Open Questions" section in main task doc.

---

**Status:** ✅ Planning Complete  
**Next:** Implementation (Coder Mode)  
**ETA:** 4-6 hours of focused work
