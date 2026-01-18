# DUPLICATE LOGS BUG - EXECUTION ROADMAP

**Issue:** Logs showing up twice in task UI  
**Status:** Tasks created, ready for execution  
**Last Updated:** 2024-01-18

---

## Quick Start (For Coder)

**Start here:** Execute **T006** first

```bash
# Execution order:
1. T006 → Add debug logging (15 min)
2. T007 → Reproduce & analyze (20 min)
3. T008 → Implement fix (30 min)
4. T009 → Verify & cleanup (15 min)
```

---

## Task Overview

| Task | Type | Priority | Time | Status |
|------|------|----------|------|--------|
| T006 | Diagnostic | HIGH | 15m | ⏳ Ready |
| T007 | Analysis | HIGH | 20m | 🔒 Blocked by T006 |
| T008 | Implementation | HIGH | 30m | 🔒 Blocked by T007 |
| T009 | Verification | MEDIUM | 15m | 🔒 Blocked by T008 |

---

## Known Information

### Root Cause (Preliminary)

Two log emission paths both call `_on_task_log`:
1. **Bridge:** `TaskRunnerBridge.log` → `_on_bridge_log` → `_on_task_log`
2. **Recovery:** `docker logs -f` → `host_log.emit` → `_on_host_log` → `_on_task_log`

### Existing Protection (Not Working)

File: `agents_runner/ui/main_window_task_recovery.py:70-72`
```python
if task_id in self._bridges:
    return  # Should skip recovery when bridge active
```

**Question:** Why isn't this working? → **T007 will answer**

### Key Files

- `agents_runner/ui/main_window_task_events.py` (log handlers)
- `agents_runner/ui/main_window_task_recovery.py` (recovery logs)
- `agents_runner/ui/bridges.py` (TaskRunnerBridge)

---

## Existing Tasks (Reference)

These tasks provide context and fallback options:

- **T001:** Investigation doc (being superseded by T006-T009)
- **T002:** Deduplication approach (fallback if needed)
- **T004:** Advanced coordination (fallback if needed)
- **T005:** Unrelated (interactive tasks implementation)

---

## Decision Points

### After T007 Completes

Based on findings, T008 will implement ONE of:

**Option A: Fix Bridge Check**
- If: `self._bridges` check is broken
- Fix: Ensure immediate bridge registration/removal
- Complexity: Low

**Option B: Simple Deduplication**
- If: Race condition unavoidable
- Fix: Track recent logs (last 100), skip if duplicate within 2s
- Complexity: Low-Medium

**Option C: Explicit Coordination**
- If: Both readers legitimately active
- Fix: Add per-task lock for log reading
- Complexity: Medium

**Option D: Disable Recovery for Active Tasks**
- If: Recovery starts too early
- Fix: Separate flag for "bridge ever connected"
- Complexity: Low

---

## Success Criteria

- ✅ No duplicate logs in UI
- ✅ All logs still captured (none lost)
- ✅ Performance unchanged
- ✅ Clean, maintainable code
- ✅ Works across app restarts

---

## Communication

**Coder:** Execute tasks sequentially, update status in each file  
**Task Master:** Check progress after each task completion  
**Reviewer:** Review code after T008 before T009  

---

## Agent Output Log

See: `/tmp/agents-artifacts/agent-output.md`

---

## Notes

- Do NOT modify `.agents/temp/` folder
- Keep commits small and focused (one per task)
- Add `[FIX]` prefix to commit messages
- Test thoroughly at each step
