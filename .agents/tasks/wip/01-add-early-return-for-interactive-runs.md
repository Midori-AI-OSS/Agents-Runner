# Task: Add early return for interactive runs in _tick_recovery_task

## Problem
Interactive runs trigger recovery_tick checks every 5 seconds and generate log spam even though they never need finalization. Note: `_reconcile_tasks_after_restart()` already filters interactive runs (line 58), but `_tick_recovery_task()` does not, creating inconsistent behavior.

## Location
File: `agents_runner/ui/main_window_task_recovery.py`
Function: `_tick_recovery_task` (lines 80-156)

## Required Change
Add early return at start of `_tick_recovery_task` before finalization_state checks:

```python
def _tick_recovery_task(self, task: Task) -> None:
    # Skip recovery for interactive runs - they don't need finalization
    if task.is_interactive_run():
        return
    
    # ... rest of existing logic
```

## Acceptance Criteria
- Interactive runs immediately return from recovery_tick (consistent with startup reconciliation)
- No log messages generated for interactive runs during recovery_tick
- Non-interactive runs continue normal recovery behavior
- Behavior matches `_reconcile_tasks_after_restart()` filtering (line 58)
- Run `uv run main.py` and verify no spam for interactive tasks

## Testing
1. Start an interactive run (`agents-runner-tui-it-*` container)
2. Check logs - should see NO recovery_tick messages for that task
3. Verify normal tasks still get recovery_tick processing
