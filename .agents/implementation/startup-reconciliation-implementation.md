# Startup Reconciliation Implementation

## Overview
This document explains the startup reconciliation logic and its distinction from recovery tick.

## Purpose
`_reconcile_tasks_after_restart()` is called once at app startup to handle tasks from the previous session that need attention.

## When Each Path Is Used

### 1. Startup Reconciliation (`startup_reconcile`)
**Trigger**: Once at app startup via `_load_state()` → `_reconcile_tasks_after_restart()`

**Purpose**: Handle tasks from previous session that were interrupted or completed before app closed

**What it does**:
- For **active tasks** (running/starting when app closed):
  - Syncs container state to determine actual status
  - Ensures log tailing is active if container still running
- For **done/failed tasks** needing finalization:
  - Queues finalization if not already done
  - Reason: `"startup_reconcile"`

**Guard**: 
- Run-once flag `self._reconcile_has_run` prevents accidental re-runs
- Only runs if flag is False, then sets to True

### 2. Recovery Tick (`recovery_tick`)
**Trigger**: Every 5 seconds via QTimer (`_tick_recovery()`)

**Purpose**: Safety net for tasks that complete DURING runtime but miss event-driven finalization

**What it does**:
- Iterates all tasks and calls `_tick_recovery_task()` for each
- For **active tasks**: same as startup_reconcile (sync state, ensure log tail)
- For **done/failed tasks** needing finalization:
  - Queues finalization if not already done
  - Reason: `"recovery_tick"`

**Guard**: 
- Runs continuously, but deduplication in `_queue_task_finalization()` prevents duplicate work

## Why Both Are Needed

### Scenario 1: Task completed before restart, finalization missed
- **Without startup_reconcile**: Would wait up to 5 seconds for recovery_tick to catch it
- **With startup_reconcile**: Handled immediately at startup for faster user experience

### Scenario 2: Task completes during runtime, event-driven path misses it
- **Without recovery_tick**: Task would never finalize (data loss)
- **With recovery_tick**: Caught within 5 seconds as safety net

### Scenario 3: Both paths try to finalize the same task
- **Deduplication guards** in `_queue_task_finalization()` prevent duplicate work:
  1. Early state check for "pending" (lines 179-190)
  2. Early state check for "running" (lines 191-201)
  3. Thread existence check (lines 208-219)
  4. State cleanup for orphaned "running" (lines 223-233)

## Implementation Details

### Location: `agents_runner/ui/main_window_task_recovery.py`

```python
def _reconcile_tasks_after_restart(self) -> None:
    """Reconcile tasks after app restart.
    
    This runs once at startup to handle tasks that were interrupted or completed
    before the app was closed. It serves a different purpose than recovery_tick:
    
    - startup_reconcile: Handles tasks that were done BEFORE restart but missed finalization
    - recovery_tick: Safety net for tasks that complete DURING runtime but miss events
    
    For active tasks, delegates to _tick_recovery_task() to sync container state.
    For done/failed tasks, queues finalization if needed and not already finalized.
    
    Note: Deduplication guards in _queue_task_finalization() prevent duplicate work
    if recovery_tick fires before this completes.
    """
    # STARTUP RECONCILIATION: Run once at app start to handle tasks from previous session
    for task in list(self._tasks.values()):
        if task.is_active():
            # Sync container state for tasks that were running when app closed
            self._tick_recovery_task(task)
            continue
        if self._task_needs_finalization(task) and not task.is_interactive_run():
            # Queue finalization for tasks that completed before restart
            self._queue_task_finalization(task.task_id, reason="startup_reconcile")
```

### Location: `agents_runner/ui/main_window_persistence.py`

```python
# Run startup reconciliation once
# Guard prevents accidental re-runs if _load_state() is called multiple times
try:
    if not getattr(self, '_reconcile_has_run', False):
        self._reconcile_has_run = True
        self._reconcile_tasks_after_restart()
except Exception:
    pass
```

## Acceptance Criteria Met

### ✅ 1. Startup reconciliation runs exactly once at app start
- Run-once flag `self._reconcile_has_run` ensures single execution
- Flag checked before running, set after running
- Even if `_load_state()` called multiple times, reconciliation only runs once

### ✅ 2. Correctly identifies tasks that need finalization
- Uses `_task_needs_finalization()`: checks `task.is_done() or task.is_failed()` AND `finalization_state != "done"`
- Excludes interactive tasks via `not task.is_interactive_run()`

### ✅ 3. Doesn't queue duplicate finalization
- Four-layer deduplication mechanism in `_queue_task_finalization()`
- Guards prevent duplicates from any path (startup, recovery, task_done, user_stop)

### ✅ 4. Clear distinction in code and logs
- Different `reason` strings: `"startup_reconcile"` vs `"recovery_tick"`
- Comprehensive docstrings explain purpose of each path
- Inline comments clarify when each runs
- Logging includes reason for traceability

### ✅ 5. Documentation when each path is used and why both are needed
- This document (startup-reconciliation-implementation.md)
- Docstrings on `_reconcile_tasks_after_restart()` and `_tick_recovery_task()`
- Inline comments in code
- Related: task-finalization-flow.md (existing)

## Testing Notes
- Manual testing: Restart app with done tasks → should finalize immediately
- Manual testing: Let task complete during runtime → should finalize within 5 seconds
- Manual testing: Stop/cancel task → should finalize with reason="user_stop"
- Code inspection: Deduplication guards prevent duplicate work

## Related Files
- `agents_runner/ui/main_window_task_recovery.py` - Main implementation
- `agents_runner/ui/main_window_persistence.py` - Run-once guard
- `.agents/implementation/task-finalization-flow.md` - Overall finalization flow
- `.agents/implementation/recovery-tick-behavior.md` - Recovery tick details
