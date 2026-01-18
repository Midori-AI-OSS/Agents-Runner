# T004: Coordinate Bridge and Recovery Log Readers

**Priority:** LOW (OPTIONAL)  
**Suggested Order:** 4 (Only if T003 insufficient)  
**Type:** Implementation (robust coordination)  
**Prerequisites:** Attempt T003 first—only do this if T003 fails

## Problem
Two independent log readers (bridge and recovery) operate simultaneously without coordination.

## Task
Add coordination between TaskRunnerBridge.log signal and recovery log tail to ensure only one is active per task.

## Implementation Details

**Note:** This approach may be over-engineered. The existing `self._bridges` dict already provides this coordination (see T003).

If T003 is insufficient, implement explicit coordination:

1. Add instance variable: `_log_reader_active: dict[str, str] = {}`  # task_id -> "bridge" | "recovery"
2. When bridge starts streaming, set `_log_reader_active[task_id] = "bridge"`
3. Recovery log tail checks this dict before starting and skips if value is "bridge"
4. When bridge stops (task ends or app shuts down), clear the entry
5. On app restart, dict is empty, so recovery can run

**Concurrency Safety:**
- All dict access must be protected with `threading.Lock`
- Qt signals are queued, so race conditions possible
- Use `QMutex` or Python `threading.Lock` for thread safety

## Files to Modify
- `agents_runner/ui/bridges.py` (TaskRunnerBridge—track active streams)
- `agents_runner/ui/main_window_task_recovery.py` (check before starting recovery)
- Possibly add shared state manager or extend existing task state tracking

## Acceptance Criteria
- Only one log reader active per task at any time
- Bridge takes precedence when available
- Recovery activates after app restart or bridge failure
- No duplicate logs
- Clean transition between modes
- Thread-safe (no race conditions or deadlocks)

## Edge Cases
- **Bridge crashes without cleanup:** Recovery must detect stale "bridge-active" flag
- **Concurrent start:** Bridge and recovery both try to start simultaneously (need lock)
- **App restart during bridge cleanup:** Flag persists in memory (not across restarts)

## Thread Safety
```python
class MainWindow:
    def __init__(self):
        self._log_reader_lock = threading.Lock()
        self._log_reader_active: dict[str, str] = {}
    
    def _start_bridge_logs(self, task_id: str):
        with self._log_reader_lock:
            self._log_reader_active[task_id] = "bridge"
    
    def _ensure_recovery_log_tail(self, task: Task):
        with self._log_reader_lock:
            if self._log_reader_active.get(task_id) == "bridge":
                return  # Bridge owns logs
        # ... start recovery
```

## Verification Steps
1. Start task—verify only bridge logs appear (not duplicated)
2. Check `_log_reader_active[task_id] == "bridge"`
3. Restart app—verify recovery starts (dict is empty)
4. Stress test: Start 10 tasks simultaneously—verify no duplicate logs
5. Kill bridge thread—verify recovery takes over within 2 seconds

## Why This May Be Unnecessary
The existing `self._bridges` dict already tracks active bridges. T003 uses this for coordination without new state. Only implement T004 if T003 proves insufficient.

## Notes
- Most robust solution but adds complexity
- May be overkill for this problem
- Consider T003 first (simpler, leverages existing state)
