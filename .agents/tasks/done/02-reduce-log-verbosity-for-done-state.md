# Task: Reduce log spam for already-finalized tasks

## Problem
Tasks with `finalization_state="done"` log a DEBUG message every 5 seconds during recovery_tick (lines 89-99). This creates unnecessary log noise. Note: Task 03 (stable task tracking) provides a comprehensive solution by preventing repeated checks entirely.

## Location
File: `agents_runner/ui/main_window_task_recovery.py`
Function: `_tick_recovery_task` (lines 89-99)

## Required Change
Remove the DEBUG log for already-done tasks (strongly recommended):

**Option 1 (Strongly Recommended):** Remove the log entirely
```python
if (task.finalization_state or "").lower() == "done":
    return  # Silent return - Task 03 will provide proper deduplication
```

**Option 2 (Not recommended):** Add throttling (Task 03 makes this obsolete)
```python
if (task.finalization_state or "").lower() == "done":
    # Only log once per task (but Task 03 is the proper solution)
    return
```

**Note:** This task provides immediate symptom relief. Task 03 (stable task tracking) addresses the root cause by preventing repeated processing of completed tasks.

## Acceptance Criteria
- No repeated logs for tasks already in finalization_state="done"
- Recovery_tick still processes active/pending tasks normally
- Log file size significantly reduced for long-running applications

## Testing
1. Run several tasks to completion
2. Let app run for 60+ seconds
3. Check logs - should NOT see repeated "skipping finalization (reason=already done)" messages
