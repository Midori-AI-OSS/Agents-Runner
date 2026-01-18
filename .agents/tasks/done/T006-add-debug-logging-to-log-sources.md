# T006: Add Debug Logging to Identify Log Sources

**Priority:** HIGH  
**Type:** Diagnostic  
**Estimated Time:** 15 minutes

## Problem

Logs are appearing twice in the UI, but the existing check in `_ensure_recovery_log_tail` (line 71-72) should prevent this. We need to understand:
1. Is the bridge check working?
2. Are both log sources active simultaneously?
3. Is there a timing/race condition?

## Task

Add temporary debug logging to identify which code path is emitting logs.

## Implementation

### File: `agents_runner/ui/main_window_task_events.py`

**Modify `_on_bridge_log` (line 278-279):**
```python
def _on_bridge_log(self, task_id: str, line: str) -> None:
    logger.debug(f"[BRIDGE LOG] task={task_id[:8]} bridge_active={task_id in self._bridges}")
    self._on_task_log(task_id, line)
```

**Modify `_on_host_log` (line 366-367):**
```python
def _on_host_log(self, task_id: str, line: str) -> None:
    logger.debug(f"[HOST LOG] task={task_id[:8]} bridge_active={task_id in self._bridges}")
    self._on_task_log(task_id, line)
```

**Modify `_on_task_log` (line 399-404):**
```python
def _on_task_log(self, task_id: str, line: str) -> None:
    task = self._tasks.get(task_id)
    if task is None:
        return
    logger.debug(f"[TASK LOG] task={task_id[:8]} line_len={len(line)} first_50={line[:50]}")
    cleaned = prettify_log_line(line)
    # ... rest of function
```

### File: `agents_runner/ui/main_window_task_recovery.py`

**Modify `_ensure_recovery_log_tail` (line 70-73):**
```python
# Skip if task has active bridge (bridge owns log streaming)
if task_id in self._bridges:
    logger.debug(f"[RECOVERY SKIP] task={task_id[:8]} reason=bridge_active")
    return
else:
    logger.debug(f"[RECOVERY START] task={task_id[:8]} container={container_id[:8]}")
```

## Testing Steps

1. Set logging level to DEBUG: Edit main entrypoint or add `logging.basicConfig(level=logging.DEBUG)`
2. Start a task that produces logs
3. Check console output for `[BRIDGE LOG]` and `[HOST LOG]` entries
4. Look for patterns:
   - Are BOTH appearing for the same task_id and log line?
   - Is `bridge_active=True` but recovery still running?
   - Is there a timing gap where bridge disconnects but recovery hasn't started?

## Expected Outcome

Debug output will clearly show:
- Which path(s) are calling `_on_task_log` for each log line
- Whether `self._bridges` check is working correctly
- Any race conditions or timing issues

## Acceptance Criteria

- Debug logging added to all 4 functions
- Log format includes task_id prefix (first 8 chars) for easy filtering
- No functional changes—only logging added
- Ready to run and diagnose in next task

## Follow-up

After running with debug logs, create T007 based on findings.
