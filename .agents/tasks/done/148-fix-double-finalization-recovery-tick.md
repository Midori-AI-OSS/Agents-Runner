# Task: Fix Double Finalization from recovery_tick (Issue #148)

## Issue Reference
- GitHub Issue: #148
- Title: "Finalize Memes with `recovery_tick`"
- Problem: Finalization is running twice - once for recovery_tick and once for task_done

## Current Behavior
Task finalization executes twice:
1. First finalization: `reason=recovery_tick`
2. Second finalization: `reason=task_done`

Example log output:
```
[host/finalize][INFO] finalization running (reason=recovery_tick)
[host/finalize][INFO] finalization complete
[host/finalize][INFO] finalization queued
[host/finalize][INFO] task marked complete: status=done exit_code=0
[host/finalize][INFO] finalization running (reason=task_done)
[host/finalize][INFO] finalization complete
```

## Root Cause Analysis Required
1. Check `agents_runner/ui/main_window_task_recovery.py` line 42 where `recovery_tick` triggers finalization
2. Review `_tick_recovery()` method (line 27-29) - this runs continuously via QTimer every 1 second
3. Check if finalization state tracking prevents duplicate runs
4. Investigate if recovery_tick should only run on startup, not continuously
5. Verify if `_task_needs_finalization()` at line 44-47 properly checks `finalization_state == "done"`

## Expected Fix
Recovery tick should only run during startup reconciliation (not continuously), or finalization should be idempotent and check if already completed before running again.

## How to Reproduce
1. Launch the Agents Runner GUI: `uv run main.py`
2. Run any agent task to completion
3. Watch the logs/console output during task finalization
4. Observe two separate finalization runs in the logs

## How to Verify
1. Launch the Agents Runner GUI: `sudo uv run main.py` (sudo required for docker socket access)
2. Run a simple agent task to completion
3. Check logs to confirm finalization only runs once
4. Restart the application and verify recovery reconciliation works correctly
5. Confirm no duplicate finalization during recovery

## Notes
- Implemented guard to skip queuing finalization in `_on_task_done` when already marked `finalization_state=done`.
- Recovery tick now returns early for tasks with `finalization_state=done`, preventing repeated queuing.

## Files to Investigate
- `agents_runner/ui/main_window_task_recovery.py` - Recovery tick and finalization triggering
- `agents_runner/ui/main_window.py` lines 138-141 - QTimer setup for recovery ticker
- `agents_runner/ui/main_window_tasks_interactive_finalize.py` - Finalization implementation
- `agents_runner/ui/task_model.py` line 47 - `finalization_state` field

## Potential Solutions
1. Only run recovery tick during startup, not continuously
2. Add finalization state check before queuing finalization
3. Make `_queue_task_finalization()` check if already queued/running
4. Add flag to track if finalization has been queued for a task

## Acceptance Criteria
- [ ] Task finalization runs exactly once per task completion
- [ ] Recovery reconciliation still works correctly on app restart
- [ ] No duplicate finalization events in logs
- [ ] Finalization state tracking prevents re-runs

---
## AUDITOR REVIEW FAILURE

**Critical Syntax Error Found**

The fix in `agents_runner/ui/main_window_task_events.py` contains a syntax error that prevents the code from running:
- Lines 559-571 were incorrectly un-indented outside the `try` block (line 504)
- This breaks the `try-finally` structure ending at line 572
- Python compilation fails with: `SyntaxError: expected 'except' or 'finally' block`

**Required Fix:**
Lines 559-571 must be properly indented to be inside the `try` block. The guard check at line 565-566 is correct logic, but it needs to be indented along with the rest of the finalization code.

**Logic Review:**
The fix logic itself is sound:
1. Adding a guard in `_tick_recovery_task()` to return early if `finalization_state == "done"` ✓
2. Adding a guard in `_on_task_done()` to skip queuing finalization if already done ✓

Both guards prevent double finalization, but the indentation error must be fixed first.
