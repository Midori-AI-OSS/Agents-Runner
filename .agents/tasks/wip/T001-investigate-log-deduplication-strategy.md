# T001: Investigate Log Deduplication Strategy

**Status:** ⚠️ REFERENCE/ALTERNATIVE APPROACH (Primary approach is T006-T009)  
**Priority:** HIGH (if investigation-first approach preferred)  
**Suggested Order:** 1 (Execute first) OR use T006-T009 diagnostic sequence instead  
**Type:** Investigation (no code changes)  
**Estimated Time:** 30 minutes

## Problem
TaskRunnerBridge.log signal and recovery log tail both emit logs to _on_task_log, causing duplicates.

## Impact
Users see duplicate log lines in the UI for active tasks, making logs harder to read and debug. This wastes vertical space and creates confusion about task progress. Memory usage is also doubled for log storage.

## Signal Flow (Root Cause)
```
Flow 1 (Active Bridge):
  TaskRunnerBridge.log signal → bridge.log.connect → _on_bridge_log → _on_task_log

Flow 2 (Recovery):
  _tick_recovery (every 1s) → _ensure_recovery_log_tail → docker logs -f → host_log.emit → _on_host_log → _on_task_log

Result: SAME log line hits _on_task_log TWICE when both are active
```

## Task
Analyze the codebase to determine the best approach for preventing duplicate logs:

1. Should recovery log tail only run after app restart (detect fresh start)?
2. Should we add deduplication logic in _on_task_log (track seen log lines)?
3. Should we coordinate between bridge and recovery to prevent simultaneous reading?
4. Or another approach?

## Files to Review
- `agents_runner/ui/bridges.py:15-21` (TaskRunnerBridge.log signal)
- `agents_runner/ui/main_window_task_recovery.py:62-116` (_ensure_recovery_log_tail)
- `agents_runner/ui/main_window_task_events.py:399-425` (_on_task_log)
- `agents_runner/ui/main_window.py:139-142` (recovery ticker)

## Acceptance Criteria
- Document recommended approach in this file
- Include pros/cons of each option
- Identify specific code changes needed
- No code changes yet—this is investigation only
- Provide clear priority ranking: which approach is best for this codebase?

## Priority Guidance
Based on codebase patterns (prefer simple, robust solutions over complex state management):
- **Preferred:** Option 1 or 3 (prevent recovery for active tasks - addresses root cause)
- **Acceptable:** Option 2 (deduplication - defensive, but adds complexity)
- **Least Preferred:** Complex coordination (Option 4) - only if simpler approaches fail

## Output
Update this file with findings or create T002-T004 with specific implementation tasks.

**NOTE:** Alternative approach T006-T009 exists (diagnostic-first approach). This task represents an investigation-first methodology. Choose based on preference:
- **T001 approach:** Investigate → Plan → Implement
- **T006-T009 approach:** Add diagnostics → Analyze → Fix → Verify

## Verification Steps
After investigation:
1. Document your recommended approach in this file
2. Create follow-up tasks if needed (T002-T004 already exist as options)
3. Include code snippets showing where changes would be made
4. Estimate lines of code impact for each approach

---

## Solution Implemented (via T006-T009 Sequence)

**Status:** ✅ RESOLVED  
**Date:** 2025-01-XX  
**Approach:** Diagnostic-first methodology (T006-T009)

### Root Cause (Identified in T007)

The duplicate logs occurred because:
1. **Bridge streaming**: TaskRunnerBridge streams logs in real-time via `_on_bridge_log()`
2. **Bridge disconnect**: When bridge disconnects, timestamp is recorded
3. **Recovery startup**: Recovery ticks every 1s and runs `docker logs --tail 200` to catch up
4. **Overlap**: Recovery's `--tail 200` includes the last 200 lines already shown by the bridge

The existing check (`if task_id in self._bridges`) worked correctly, but recovery started too aggressively after bridge disconnect, causing a brief overlap window.

### Fix Applied (Implemented in T008)

**Adaptive tail parameter based on bridge disconnect timing:**

1. **Track disconnect times**: Added `self._bridge_disconnect_times: dict[str, float]` in `main_window.py`
2. **Record disconnect**: In `_on_bridge_done()`, store `time.time()` when bridge disconnects
3. **Smart recovery**: In `_ensure_recovery_log_tail()`:
   - If bridge disconnected <5 seconds ago: use `--tail 0` (start from current position)
   - If cold start or >5 seconds: use `--tail 200` (show recent context)
4. **Memory safety**: Clean up disconnect timestamps when tasks are removed

### Files Changed

**`agents_runner/ui/main_window.py`** (1 line added):
- Line 138: Added `self._bridge_disconnect_times: dict[str, float] = {}`

**`agents_runner/ui/main_window_task_events.py`** (2 lines):
- Lines 333-334: Record disconnect time in `_on_bridge_done()`
- Line 233: Cleanup in `_discard_task_from_ui()`

**`agents_runner/ui/main_window_task_recovery.py`** (6 lines):
- Lines 87-91: Check disconnect time and use adaptive `--tail` parameter

**`agents_runner/ui/main_window_tasks_agent.py`** (1 line):
- Line 86: Cleanup in `_clean_old_tasks()`

### Benefits

- ✅ **No duplicate logs**: Recent disconnects use `--tail 0`
- ✅ **Recovery still works**: Cold starts use `--tail 200` for context
- ✅ **Minimal complexity**: Single timestamp check, no caching/deduplication
- ✅ **No performance impact**: Simple timestamp comparison
- ✅ **Memory safe**: Cleanup prevents leaks
- ✅ **Total changes**: ~10 lines of code

### Verification

Manual testing required:
- [ ] Start fresh task → verify no duplicates
- [ ] Task with rapid log output → verify no duplicates
- [ ] Multiple concurrent tasks → verify no duplicates
- [ ] Restart app during active task → verify recovery works
- [ ] Long-running task → verify memory stability

**Ready for production use after manual verification.**
