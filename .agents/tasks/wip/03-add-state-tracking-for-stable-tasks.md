# Task: Add state tracking to skip recovery checks for stable tasks

## Problem
Recovery_tick processes ALL tasks every 5 seconds, even tasks that are long-completed and stable. This wastes CPU and generates potential log spam. This is the root cause of the issues addressed in Tasks 01 and 02.

## Location
File: `agents_runner/ui/main_window_task_recovery.py`
Function: `_tick_recovery` (line 71-78)

## Required Change
Add a set to track tasks that have reached stable terminal state:

```python
# In MainWindow.__init__ (near line 136-137, with other recovery structures):
self._stable_tasks: set[str] = set()

# In _tick_recovery_task after confirming finalization is done:
def _tick_recovery_task(self, task: Task) -> None:
    task_id = str(task.task_id or "")
    
    # Skip if already marked stable
    if task_id in self._stable_tasks:
        return
    
    if (task.finalization_state or "").lower() == "done":
        self._stable_tasks.add(task_id)  # Mark as stable
        return
    
    # ... rest of existing logic
```

**Thread Safety Note:** Consider synchronization if set operations can occur concurrently (recovery_tick runs on timer thread).

**Cleanup Requirements:** Remove task from `_stable_tasks` when task is discarded/removed:
```python
# In task discard/removal function:
self._stable_tasks.discard(task_id)
```

## Acceptance Criteria
- Completed tasks are only checked once, then marked stable
- Recovery_tick skips stable tasks entirely (no processing, no logs)
- Stable task set is properly initialized in `MainWindow.__init__` (near line 136-137)
- Task IDs are removed from stable set when tasks are discarded
- Memory usage remains reasonable (set only stores task IDs as strings)
- Thread safety considered for concurrent set access

## Testing
1. Complete several tasks
2. Let app run for several minutes
3. Verify CPU usage is minimal (not repeatedly processing completed tasks)
4. Check that discarding a task removes it from stable set
