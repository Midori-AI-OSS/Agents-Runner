# Recovery Tick Behavior Analysis

## Overview
The recovery ticker is a QTimer that runs every 5000ms (5 seconds) to monitor and recover tasks that may have been interrupted or need finalization after app restart or state changes.

**Note**: The interval was increased from 1 second to 5 seconds to reduce check frequency by 80% while maintaining full safety net functionality. See `.agents/implementation/recovery-tick-timing-analysis.md` for detailed rationale.

## Current Implementation

### Timer Setup
Location: `agents_runner/ui/main_window.py`
```python
self._recovery_ticker = QTimer(self)
self._recovery_ticker.setInterval(5000)  # 5 seconds (reduced from 1 second)
self._recovery_ticker.timeout.connect(self._tick_recovery)
self._recovery_ticker.start()
```

### Recovery Flow
Location: `agents_runner/ui/main_window_task_recovery.py`

#### Main Entry Points
1. **_tick_recovery()** (line 27-29)
   - Called every 5 seconds by the timer (reduced from 1 second)
   - Iterates through all tasks and calls `_tick_recovery_task()` for each

2. **_reconcile_tasks_after_restart()** (line 19-25)
   - Called once at app startup
   - Handles tasks that were active or incomplete when app was closed
   - Calls `_tick_recovery_task()` for active tasks
   - Queues finalization for incomplete non-interactive tasks with reason="startup_reconcile"

#### Task Recovery Logic
**_tick_recovery_task(task)** (line 31-46)

Early exit conditions:
- Returns immediately if `finalization_state == "done"` (line 33-34)

Behavior for active/unknown tasks:
- Attempts to sync container state (line 38-40)
- Updates UI if sync succeeded (line 39-40)
- Ensures recovery log tail is running (line 42)
- Returns without finalization (line 43)

Finalization trigger:
- If task needs finalization AND is not interactive, queues finalization with reason="recovery_tick" (line 45-46)

### Finalization Queueing
**_queue_task_finalization(task_id, *, reason)** (line 120-145)

Guards:
1. Returns early if task_id is empty (line 121-123)
2. Returns if task is None (line 125-127)
3. Returns if task doesn't need finalization (line 129-130)
4. Returns if a finalization thread is already alive (line 132-134)
5. Resets state from "running" to "pending" if needed (line 136-137)

Then starts a new finalization thread.

### Finalization Need Check
**_task_needs_finalization(task)** (line 48-51)
- Returns False if task is not done or failed
- Returns True if finalization_state != "done"

### Finalization States
- "pending": Task needs finalization but hasn't started yet
- "running": Finalization is actively in progress
- "done": Finalization completed successfully
- "error": Finalization encountered an error

## All Finalization Trigger Points

1. **"task_done"** (main_window_task_events.py:571)
   - When bridge/runner completes successfully or with error
   - Called from `_on_task_done()` after task is marked complete
   - Sets finalization_state to "pending" before queueing (line 568-570)
   - Early exits if finalization_state is already "done" (line 565-566)

2. **"user_stop"** (main_window_task_events.py:134)
   - When user stops or kills a task
   - Called from `_on_task_container_action()` for stop/kill actions
   - Sets finalization_state to "pending" before queueing (line 131-133)

3. **"recovery_tick"** (main_window_task_recovery.py:46)
   - Called every 5 seconds by recovery timer for incomplete tasks (reduced from 1 second)
   - Only triggers if task is done/failed, not interactive, and finalization_state != "done"

4. **"startup_reconcile"** (main_window_task_recovery.py:25)
   - Called once at app startup
   - For tasks that need finalization and are not interactive

## Root Cause: Why Multiple recovery_tick Finalizations Occur

### The Issue
Based on issues #148 and #155, the recovery_tick is triggering finalization multiple times when it should only trigger once (if at all).

### Analysis

The problem occurs when:
1. A task completes via bridge (`_on_task_done()` with reason="task_done")
2. Finalization is queued with reason="task_done"
3. Recovery ticker ticks (every 1 second)
4. `_tick_recovery_task()` checks if task needs finalization
5. Even though finalization was already queued, the state might still be "pending"
6. The guard in `_queue_task_finalization()` at line 132-134 checks if thread is alive
7. If the task_done finalization hasn't started yet or just finished, the thread may not exist or be dead
8. Result: recovery_tick queues another finalization

### Race Condition
There's a window between:
- Setting finalization_state = "pending" (task_events.py:568)
- Starting the finalization thread (task_recovery.py:145)
- The recovery ticker checking the task (every 1 second)

If recovery_tick checks during this window, it sees:
- Task is done/failed ✓
- finalization_state != "done" ✓ (it's "pending")
- Thread doesn't exist or isn't alive ✓
- Result: Queues duplicate finalization

### Special Case: Recovery Tick Skips Cleanup
Line 242-250 in `_finalize_task_worker()` shows special handling:
```python
if (
    not pr_worker_ran
    and reason != "recovery_tick"  # Skip cleanup during recovery
    and task.workspace_type == WORKSPACE_CLONED
    ...
):
    self._cleanup_task_workspace_for_finalization(...)
```

This suggests recovery_tick finalization is expected to run but should skip workspace cleanup. However, this doesn't explain why it runs multiple times.

## When recovery_tick SHOULD Trigger Finalization

1. **App Restart Scenario**
   - App was closed while task was running
   - Task container exited while app was down
   - Task status shows done/failed but finalization_state != "done"
   - Recovery ticker discovers this and triggers finalization

2. **Container State Sync**
   - Task running but bridge disconnected
   - Container exits independently
   - `_try_sync_container_state()` updates status to done/failed
   - Recovery ticker sees status change and triggers finalization

3. **Missed Bridge Done Signal**
   - Bridge fails to emit done signal
   - Task completes but `_on_task_done()` never called
   - Recovery ticker acts as safety net

## When recovery_tick SHOULD NOT Trigger Finalization

1. **Normal Task Completion**
   - Task completes via bridge
   - `_on_task_done()` already queued finalization with reason="task_done"
   - recovery_tick should recognize finalization is already queued/running

2. **User-Stopped Tasks**
   - User clicked stop/kill
   - `_on_task_container_action()` already queued finalization with reason="user_stop"
   - recovery_tick should not duplicate this

3. **Already Finalized Tasks**
   - finalization_state == "done"
   - Current code correctly handles this (early return at line 33-34)

4. **Interactive Tasks**
   - `is_interactive_run()` returns True
   - Current code correctly handles this (check at line 45)

## The Problem

The current guard in `_queue_task_finalization()` is insufficient:
```python
existing = self._finalization_threads.get(task_id)
if existing is not None and existing.is_alive():
    return
```

This only prevents queueing if a thread exists AND is alive. It doesn't prevent:
- Queueing when finalization hasn't started yet (thread doesn't exist)
- Queueing when finalization just finished (thread exists but is dead)
- Distinguishing between a fresh task needing finalization vs a task already being processed

## Recommendations

### Option 1: Check finalization_state More Carefully
Prevent recovery_tick from queueing if finalization_state is "pending" or "running":
```python
def _tick_recovery_task(self, task: Task) -> None:
    if (task.finalization_state or "").lower() in {"done", "pending", "running"}:
        return
    # ... rest of logic
```

### Option 2: Add Timestamp Tracking
Track when finalization was last queued to prevent rapid re-queueing:
```python
# Add to class
self._finalization_queued_at: dict[str, float] = {}

def _queue_task_finalization(self, task_id: str, *, reason: str) -> None:
    # ... existing guards ...
    
    # Don't re-queue too soon
    last_queued = self._finalization_queued_at.get(task_id, 0.0)
    if time.time() - last_queued < 5.0:  # 5 second cooldown
        return
    
    self._finalization_queued_at[task_id] = time.time()
    # ... start thread
```

### Option 3: recovery_tick Only for Recovery Cases
Make recovery_tick more selective - only trigger for tasks that likely need recovery:
- Check if task status changed recently without finalization being queued
- Only act if no task_done or user_stop finalization was recently initiated

### Option 4 (Recommended): State Machine Approach
Treat finalization as a proper state machine:
- "none": Task not complete yet
- "pending": Finalization queued but not started
- "running": Finalization in progress
- "done": Finalization complete
- "error": Finalization failed

And enforce that recovery_tick only acts on "none" state for completed tasks.

## Code Snippets

### Current finalization_state Check (Too Lenient)
```python
# main_window_task_recovery.py:33-34
if (task.finalization_state or "").lower() == "done":
    return
```
Only blocks if "done", allows "pending" and "running" to proceed.

### Current _task_needs_finalization
```python
# main_window_task_recovery.py:48-51
def _task_needs_finalization(self, task: Task) -> bool:
    if not (task.is_done() or task.is_failed()):
        return False
    return (task.finalization_state or "").lower() != "done"
```
Returns True for any non-"done" state including "pending" and "running".

### Current Thread Guard
```python
# main_window_task_recovery.py:132-134
existing = self._finalization_threads.get(task_id)
if existing is not None and existing.is_alive():
    return
```
Only prevents queueing if thread exists and is alive, not if already queued.
