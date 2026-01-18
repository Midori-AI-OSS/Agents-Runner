# T001: Investigate Log Deduplication Strategy

**Priority:** HIGH  
**Suggested Order:** 1 (Execute first)  
**Type:** Investigation (no code changes)

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

## Verification Steps
After investigation:
1. Document your recommended approach in this file
2. Create follow-up tasks if needed (T002-T004 already exist as options)
3. Include code snippets showing where changes would be made
4. Estimate lines of code impact for each approach
