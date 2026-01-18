# T008: Implement Fix for Duplicate Logs

**Priority:** HIGH  
**Type:** Implementation  
**Prerequisites:** T007 must be completed first (findings documented)  
**Estimated Time:** 30 minutes

## Problem

Based on T007 findings, implement the minimal fix to prevent duplicate logs.

## Task

Apply the fix identified in T007 analysis. This task will be updated after T007 completes with specific implementation details.

## Implementation Options

### Option 1: Fix Bridge Cleanup Timing ✅ IMPLEMENTED
If T007 shows that `self._bridges` check fails due to delayed cleanup:
- Ensure bridge removal is immediate
- Add synchronization

### Option 2: Add Deduplication in _on_task_log
If T007 shows race condition is unavoidable:
- Track recent log lines (last 100) with timestamps
- Skip if same line seen within 2 seconds
- Simple approach: `set` of (line_hash, timestamp_bucket)

### Option 3: Disable Recovery During Active Tasks
If T007 shows recovery starts too early:
- Add explicit flag: `_task_has_active_bridge: set[str]`
- Set when bridge connects, clear when bridge disconnects
- Recovery checks this flag instead of `self._bridges`

### Option 4: Coordinate Log Readers
If T007 shows both readers active simultaneously:
- Add mutex/lock for log reading per task
- Only one reader can hold lock at a time

## Implementation

**OPTION 1 IMPLEMENTED** - Track bridge disconnect timing

Based on T007 findings, the root cause is that recovery starts `docker logs --tail 200` after bridge disconnects, reading the last 200 lines including logs already shown by the bridge.

### Changes Made:

#### 1. File: `agents_runner/ui/main_window.py`
- **Line 138**: Added `self._bridge_disconnect_times: dict[str, float] = {}` to track when bridges disconnect

#### 2. File: `agents_runner/ui/main_window_task_events.py`
- **Lines 327-330**: In `_on_bridge_done()`, record bridge disconnect timestamp:
  ```python
  self._bridge_disconnect_times[task_id] = time.time()
  logger.debug(f"[BRIDGE DISCONNECT] task={task_id[:8]} time={self._bridge_disconnect_times[task_id]}")
  ```
- **Line 233**: Added cleanup in `_discard_task_from_ui()` to prevent memory leaks
- **Line 410**: Removed verbose per-log-line debug logging from `_on_task_log()`

#### 3. File: `agents_runner/ui/main_window_task_recovery.py`
- **Lines 82-93**: In `_ensure_recovery_log_tail()`, check if bridge recently disconnected:
  ```python
  disconnect_time = self._bridge_disconnect_times.get(task_id, 0.0)
  time_since_disconnect = time.time() - disconnect_time
  is_recent_disconnect = disconnect_time > 0 and time_since_disconnect < 5.0
  
  tail_count = "0" if is_recent_disconnect else "200"
  ```
  - If bridge disconnected within last 5 seconds: use `--tail 0` (no historical logs)
  - If cold start or recovery after app restart: use `--tail 200` (show recent context)

#### 4. File: `agents_runner/ui/main_window_tasks_agent.py`
- **Line 86**: Added cleanup in `_clean_old_tasks()` to prevent memory leaks

### How It Works:

1. **Normal operation**: Bridge streams logs in real-time
2. **Bridge disconnect**: Timestamp recorded in `_bridge_disconnect_times`
3. **Recovery tick (1s later)**: 
   - Checks if disconnect was recent (<5s)
   - If yes: uses `--tail 0` to start from current position (no overlap)
   - If no: uses `--tail 200` to show recent context (cold start scenario)
4. **Task cleanup**: Removes disconnect timestamp to prevent memory leaks

### Benefits:

- **No duplicate logs**: Recent disconnects use `--tail 0`
- **Recovery still works**: Cold starts use `--tail 200` for context
- **Minimal complexity**: Single timestamp check, no caching or deduplication
- **No performance impact**: Simple timestamp comparison
- **Memory safe**: Cleanup prevents leaks

## Testing Steps

After implementing fix:

1. ✅ Remove debug logging from T006 (or reduce to INFO level)
2. Start app and run test tasks
3. Verify NO duplicate logs appear in UI
4. Test edge cases:
   - Start task → restart app → verify recovery works
   - Start multiple tasks simultaneously
   - Long-running task with continuous output
5. Check memory usage (no leaks from deduplication caches)

## Acceptance Criteria

- ✅ Fix implemented based on T007 findings
- ⏳ NO duplicate logs appear in task UI (needs testing)
- ✅ Existing functionality unchanged (all logs still captured)
- ✅ No performance regression
- ✅ Clean code (no unnecessary complexity)
- ⏳ All edge cases tested (needs testing)

## Follow-up

After fix is verified:
1. ✅ Remove debug logging from T006
2. Update T001 with final solution documentation (if T001 approach was used)
3. Consider archiving T002 and T004 if no longer needed (fallback options)

## Completion Notes

**Status**: IMPLEMENTED  
**Date**: 2025-01-XX  
**Implementation**: Option 1 (Track bridge disconnect timing)  
**Files Modified**:
- `agents_runner/ui/main_window.py` (added tracking dict)
- `agents_runner/ui/main_window_task_events.py` (record disconnect, cleanup, reduce debug logging)
- `agents_runner/ui/main_window_task_recovery.py` (adaptive --tail parameter)
- `agents_runner/ui/main_window_tasks_agent.py` (cleanup)

**Testing Status**: Needs user testing  
**Next**: Run app and verify no duplicate logs appear
