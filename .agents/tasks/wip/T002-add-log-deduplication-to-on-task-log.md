# T002: Add Log Deduplication to _on_task_log

**Priority:** MEDIUM  
**Suggested Order:** 3 (Execute if T003 insufficient)  
**Type:** Implementation (defensive fix)  
**Prerequisites:** Read T001 findings first

## Problem
_on_task_log receives duplicate logs from both TaskRunnerBridge and recovery log tail.

## Task
Add deduplication logic to _on_task_log to prevent the same log line from being appended twice.

## Implementation Details
In `agents_runner/ui/main_window_task_events.py:399-425`:

1. Add a per-task deduplication cache using `collections.deque` with `maxlen=500`
2. Store tuple: `(log_line_hash, timestamp)` to handle legitimate repeats
3. Before appending, check if log line hash exists in cache AND timestamp < 5 seconds ago
4. Skip if duplicate, otherwise append and add to cache
5. Use `hashlib.blake2b` for fast hashing (avoid collision attacks)

**Data Structure:**
```python
self._log_dedup_cache: dict[str, deque] = {}  # task_id -> deque of (hash, timestamp)
```

**Performance Impact:** ~5-10% overhead for log processing (hashing + deque operations)

## Files to Modify
- `agents_runner/ui/main_window_task_events.py` (_on_task_log function)

## Acceptance Criteria
- No duplicate log lines appear in task output
- Memory usage remains bounded (max 500 entries per task)
- Existing log functionality still works
- Legitimate repeated logs (e.g., "Waiting...") are NOT incorrectly filtered after 5s
- Test with both bridge logs and recovery logs active

## Edge Cases
- Legitimately repeated log lines (e.g., progress indicators) should appear if > 5s apart
- Hash collisions: Use 64-bit hash to minimize risk
- Task with > 500 unique log lines per 5s: Older entries roll off (acceptable)

## Verification Steps
1. Start a task that produces logs
2. Verify no duplicate lines appear in UI
3. Check memory: `len(self._log_dedup_cache[task_id])` should never exceed 500
4. Test with task that legitimately logs same line repeatedly (should appear after 5s delay)
5. Restart app during active task—verify dedup cache rebuilds correctly

## Notes
- This is a defensive approach—fixes symptom but not root cause
- Consider T003 as a better root cause fix
- If T003 works, this task may be unnecessary
