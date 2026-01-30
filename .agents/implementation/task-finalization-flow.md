# Task Finalization Flow Documentation

## Overview
This document traces the complete flow of task finalization in the Agents Runner application, from trigger to completion.

## Finalization State Machine

### States
1. **pending** - Task needs finalization but hasn't started yet
2. **running** - Finalization is currently in progress
3. **done** - Finalization completed successfully
4. **error** - Finalization encountered an error

### State Transitions

```
Initial State: "pending" (default in Task model)
    ↓
User/System Trigger
    ↓
_queue_task_finalization() called
    ↓
Check if finalization needed
    ↓
Set state to "pending" (if was "running")
    ↓
Create finalization thread
    ↓
_finalize_task_worker() starts
    ↓
State → "running"
    ↓
Execute finalization steps:
  1. Collect artifacts (if not user_stop)
  2. Determine if PR should be created
  3. Call _finalize_gh_management_worker() if needed
  4. Clean up workspace (if needed)
    ↓
Success → State → "done"
Error → State → "error" (with finalization_error set)
```

### Special Case: Interactive Tasks
Interactive tasks skip the standard finalization flow and set state directly to "done" in `_on_interactive_finished()` (main_window_tasks_interactive_finalize.py:45).

## Finalization Triggers

### Trigger Points (4 total)

| Trigger | Location | Reason String | Purpose | Conditions |
|---------|----------|---------------|---------|------------|
| 1. Task Completion | `main_window_task_events.py:571` | `"task_done"` | Triggered when a task completes normally (via `_on_task_done()`) | Task is done/failed and finalization_state != "done" |
| 2. User Stop/Cancel | `main_window_task_events.py:134` | `"user_stop"` | Triggered when user stops or kills a task | User clicked stop/kill button in `_on_task_container_action()` |
| 3. Startup Reconciliation | `main_window_task_recovery.py:25` | `"startup_reconcile"` | Triggered at app startup to finalize tasks that were done but not finalized | Task is done/failed, not interactive, and needs finalization |
| 4. Recovery Tick | `main_window_task_recovery.py:46` | `"recovery_tick"` | Triggered every 5 seconds by recovery timer to catch missed finalizations | Task is done/failed, not interactive, and needs finalization |

### Trigger Flow Details

#### 1. Task Completion (task_done)
**Path**: Bridge signals completion → `_on_bridge_done()` → `_on_task_done()` → `_queue_task_finalization()`

**Code Flow**:
```
main_window_task_events.py:319-364 (_on_bridge_done)
  → main_window_task_events.py:498-573 (_on_task_done)
    → Lines 565-571: Check finalization_state != "done"
    → Set finalization_state = "pending"
    → Call _queue_task_finalization(task_id, reason="task_done")
```

#### 2. User Stop/Cancel (user_stop)
**Path**: User clicks stop/kill → `_on_task_container_action()` → `_queue_task_finalization()`

**Code Flow**:
```
main_window_task_events.py:52-136 (_on_task_container_action)
  → Lines 70-136: Handle stop/kill action
    → Set task.status to "cancelled" or "killed"
    → Line 131: Set finalization_state = "pending"
    → Line 134: Call _queue_task_finalization(task_id, reason="user_stop")
```

#### 3. Startup Reconciliation (startup_reconcile)
**Path**: App startup → `_load_state()` → `_reconcile_tasks_after_restart()` → `_queue_task_finalization()`

**Code Flow**:
```
main_window_task_recovery.py:19-25 (_reconcile_tasks_after_restart)
  → Iterate all tasks
  → Line 24: Check if task needs finalization and is not interactive
  → Line 25: Call _queue_task_finalization(task.task_id, reason="startup_reconcile")
```

#### 4. Recovery Tick (recovery_tick)
**Path**: Timer fires every 5 seconds → `_tick_recovery()` → `_tick_recovery_task()` → `_queue_task_finalization()`

**Code Flow**:
```
main_window.py:144: Recovery ticker setup (5000ms interval, reduced from 1000ms)
  ↓
main_window_task_recovery.py:27-29 (_tick_recovery)
  → Iterate all tasks
  → Call _tick_recovery_task(task) for each
    ↓
main_window_task_recovery.py:31-46 (_tick_recovery_task)
  → Line 34: Skip if finalization_state == "done"
  → Lines 37-43: Try to sync container state if active
  → Line 45: Check if task needs finalization and is not interactive
  → Line 46: Call _queue_task_finalization(task.task_id, reason="recovery_tick")
```

## Finalization Process

### Entry Point: `_queue_task_finalization()`
**Location**: `main_window_task_recovery.py:120-145`

**Logic**:
1. Validate task_id and retrieve task
2. Check if finalization is needed via `_task_needs_finalization()`
3. Check if finalization thread already exists and is alive
4. If state was "running", reset to "pending" (line 137)
5. Create new daemon thread for `_finalize_task_worker()`
6. Store thread in `_finalization_threads` dict
7. Start thread

### Helper: `_task_needs_finalization()`
**Location**: `main_window_task_recovery.py:48-51`

**Logic**:
```python
def _task_needs_finalization(self, task: Task) -> bool:
    if not (task.is_done() or task.is_failed()):
        return False
    return (task.finalization_state or "").lower() != "done"
```

Returns True only if:
- Task status is done/failed/cancelled/killed, AND
- finalization_state is not "done"

### Worker: `_finalize_task_worker()`
**Location**: `main_window_task_recovery.py:147-266`

**Steps**:
1. **Initialize** (lines 149-158)
   - Set finalization_state = "running"
   - Clear finalization_error
   - Schedule save
   - Log start with reason

2. **Artifact Collection** (lines 161-202)
   - Skip if user_stop (cancelled/killed)
   - Get timeout from runner_config (default 30s)
   - Call `collect_artifacts_from_container_with_timeout()`
   - Emit host_artifacts signal if artifacts found
   - Log completion time and count

3. **PR Creation Decision** (lines 204-217)
   - Determine if PR should be created
   - Skip if:
     - user_stop (line 206-207)
     - workspace_type != WORKSPACE_CLONED (line 208-209)
     - Missing gh_repo_root (line 210-211)
     - Missing gh_branch (line 212-213)
     - PR already exists (line 214-215)
   - Otherwise, should_create_pr = True

4. **PR Creation** (lines 219-238)
   - If should_create_pr, call `_finalize_gh_management_worker()` (synchronously)
   - Otherwise, log skip reason

5. **Cleanup** (lines 240-250)
   - If PR worker did NOT run AND reason != "recovery_tick" AND workspace is cloned:
     - Call `_cleanup_task_workspace_for_finalization()`

6. **Success** (lines 252-258)
   - Set finalization_state = "done"
   - Clear finalization_error
   - Schedule save
   - Log completion

7. **Error Handling** (lines 259-266)
   - Catch any exception
   - Set finalization_state = "error"
   - Set finalization_error with exception message
   - Schedule save
   - Log error

### PR Creation Worker: `_finalize_gh_management_worker()`
**Location**: `main_window_tasks_interactive_finalize.py:98-265`

**Steps**:
1. Validate inputs
2. Pre-flight validation (check git status, gh CLI, etc.)
3. Check for existing PR
4. Prepare PR metadata (title, body, agent info)
5. Call `commit_push_and_pr()` from gh_management module
6. Update task.gh_pr_url if successful
7. **Finally block** (lines 236-265):
   - Always clean up task workspace via `cleanup_task_workspace()`
   - This ensures each task gets a fresh clone

### Cleanup Helper: `_cleanup_task_workspace_for_finalization()`
**Location**: `main_window_task_recovery.py:268-300`

**Logic**:
- Validates env_id and state_path
- Calls `cleanup_task_workspace()` from environments.cleanup module
- Logs cleanup status

## Thread Management

### Finalization Threads Dictionary
**Location**: `main_window.py:137`
```python
self._finalization_threads: dict[str, threading.Thread] = {}
```

**Purpose**: Tracks active finalization threads by task_id

**Usage**:
- **Store**: `main_window_task_recovery.py:144` - Thread stored when created
- **Check**: `main_window_task_recovery.py:132` - Check if thread exists and is alive before creating new one
- No explicit cleanup - threads are daemon threads that exit when worker completes

**Race Condition Protection**:
- Lines 132-134: Check if existing thread is alive before creating new one
- This prevents multiple finalization threads for the same task

## Race Conditions Analysis

### Potential Race Conditions

#### 1. Multiple Triggers for Same Task ✅ PROTECTED
**Scenario**: Task completes while recovery tick is running

**Protection**: 
- `_queue_task_finalization()` checks if thread already exists (line 132)
- Only creates new thread if existing thread is not alive
- Result: Safe - only one finalization runs at a time per task

#### 2. State Transitions During Finalization ⚠️ POTENTIAL ISSUE
**Scenario**: Task state changes while finalization is running

**Current Behavior**:
- finalization_state is set to "running" at start of worker (line 152)
- finalization_state is set to "done" at end of worker (line 252)
- No locks protect these state changes

**Potential Issue**:
- If `_queue_task_finalization()` is called while worker is between lines 152-252:
  - Line 137 checks if state is "running" and resets to "pending"
  - But thread check (line 132) prevents new thread
  - Result: State might be inconsistent but no duplicate work

**Risk Level**: LOW - Thread check prevents actual problem, but state could be confusing

#### 3. Recovery Tick During PR Creation ⚠️ EDGE CASE
**Scenario**: recovery_tick fires while PR creation is in progress

**Current Behavior**:
- PR creation happens synchronously in finalization worker
- finalization_state stays "running" during entire PR creation
- recovery_tick checks finalization_state (line 34) and skips if "running"

**Issue**:
- Line 137 might reset "running" to "pending" if somehow called
- But thread check (line 132) prevents new worker thread

**Risk Level**: LOW - Protected by thread check

#### 4. Workspace Cleanup Race ⚠️ POTENTIAL ISSUE
**Scenario**: Multiple cleanup calls for same task workspace

**Locations**:
- `_finalize_task_worker()` line 247-250
- `_finalize_gh_management_worker()` finally block line 236-261
- `_discard_task_from_ui()` line 263-273

**Current Behavior**:
- No locking around cleanup operations
- cleanup_task_workspace() is called from multiple places

**Protection**:
- cleanup_task_workspace() is idempotent (safe to call multiple times)
- Filesystem operations are atomic at OS level

**Risk Level**: LOW - Idempotent operations are safe

### Summary of Race Condition Safety

| Scenario | Protected By | Risk Level | Notes |
|----------|--------------|------------|-------|
| Multiple finalization triggers | Thread existence check | LOW | Well protected |
| State transitions during finalization | Thread check (indirect) | LOW | State might be confusing but no functional issue |
| Recovery tick during PR | finalization_state check + thread check | LOW | Well protected |
| Multiple workspace cleanups | Idempotent operations | LOW | Safe by design |

**Overall Assessment**: The finalization system is reasonably safe from race conditions. The primary protection is the thread existence check in `_queue_task_finalization()`.

## Special Behaviors

### Interactive Tasks
- Interactive tasks do NOT use the standard finalization flow
- finalization_state is set directly to "done" in `_on_interactive_finished()` (main_window_tasks_interactive_finalize.py:45)
- They may still trigger PR creation via user dialog (lines 68-96)

### Recovery Tick vs Other Triggers
- Recovery tick skips workspace cleanup (line 242 check)
- This prevents cleanup during normal recovery monitoring
- Cleanup only happens on actual finalization events (task_done, user_stop, startup_reconcile)

### Finalization State Checks
- All trigger points check `finalization_state != "done"` before queuing
- Recovery tick adds early exit if state is "done" (line 34)
- This prevents redundant finalization work

## Files Involved

### Core Files
1. **main_window_task_recovery.py** (301 lines)
   - Contains main finalization logic
   - `_queue_task_finalization()` - Entry point
   - `_finalize_task_worker()` - Main worker
   - `_task_needs_finalization()` - Helper
   - Recovery tick system

2. **main_window_task_events.py** (659 lines)
   - Task lifecycle events
   - `_on_task_done()` - Normal completion trigger
   - `_on_task_container_action()` - User stop trigger
   - Bridge signal handlers

3. **main_window_tasks_interactive_finalize.py** (266 lines)
   - Interactive task completion
   - `_on_interactive_finished()` - Interactive completion
   - `_finalize_gh_management_worker()` - PR creation

4. **task_model.py** (180 lines)
   - Task data structure
   - Lines 47-48: finalization_state and finalization_error fields
   - Helper methods: is_done(), is_failed(), is_active()

5. **main_window.py** (200+ lines)
   - Main window initialization
   - Line 137: _finalization_threads dict
   - Lines 138-141: Recovery ticker setup

### Supporting Files
- **artifacts.py** - Artifact collection logic
- **gh_management.py** - PR creation logic
- **environments/cleanup.py** - Workspace cleanup
- **ui/task_git_metadata.py** - Git metadata validation

## Key Data Structures

### Task Model Finalization Fields
```python
finalization_state: str = "pending"  # pending|running|done|error
finalization_error: str = ""         # Error message if state is "error"
```

### Thread Tracking
```python
self._finalization_threads: dict[str, threading.Thread] = {}
```
- Key: task_id
- Value: Thread object running finalization

### Recovery System
```python
self._recovery_log_stop: dict[str, threading.Event] = {}
self._recovery_ticker = QTimer(self)  # Fires every 5000ms (5 seconds)
```

## Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                      FINALIZATION TRIGGERS                       │
└─────────────────────────────────────────────────────────────────┘
                               │
                               │
        ┌──────────────────────┼──────────────────────┐
        │                      │                      │
        │                      │                      │
        ▼                      ▼                      ▼
   task_done              user_stop            startup_reconcile
  (task completes)     (user stops task)      (app startup)
        │                      │                      │
        │                      │                      │
        └──────────────────────┴──────────────────────┘
                               │
                               ▼
                     ┌─────────────────┐
                     │ recovery_tick   │◄─── (timer, every 5s)
                     │ (every second)  │
                     └─────────────────┘
                               │
                               ▼
        ┌──────────────────────────────────────────┐
        │  _queue_task_finalization(task_id)       │
        │  • Validate task                         │
        │  • Check _task_needs_finalization()      │
        │  • Check if thread already running       │
        │  • Create finalization thread            │
        └──────────────────────────────────────────┘
                               │
                               ▼
        ┌──────────────────────────────────────────┐
        │  _finalize_task_worker(task_id, reason)  │
        │  • Set state = "running"                 │
        │  • Collect artifacts (if not user_stop)  │
        │  • Decide if PR needed                   │
        │  • Create PR if needed                   │
        │  • Cleanup workspace                     │
        │  • Set state = "done" or "error"         │
        └──────────────────────────────────────────┘
                               │
                               ▼
        ┌──────────────────────────────────────────┐
        │  _finalize_gh_management_worker()        │
        │  (if PR creation needed)                 │
        │  • Validate prerequisites                │
        │  • Check for existing PR                 │
        │  • Prepare PR metadata                   │
        │  • Create PR via gh CLI                  │
        │  • Cleanup workspace                     │
        └──────────────────────────────────────────┘
                               │
                               ▼
                        ┌──────────┐
                        │   DONE   │
                        └──────────┘
```

## Related Issues

### Issue #148: Finalize Memes with `recovery_tick`
- **Context**: Tasks not being finalized after completion
- **Root Cause**: Missing finalization triggers
- **Solution**: recovery_tick mechanism (lines 27-46 in main_window_task_recovery.py)

### Issue #155: More memes with `recovery_tick`
- **Context**: Additional finalization edge cases
- **Root Cause**: Various scenarios where finalization was skipped
- **Solution**: Enhanced recovery_tick checks and startup_reconcile

## Recommendations

### For Future Improvements

1. **Add explicit state locking**
   - Consider using threading.Lock() for finalization_state transitions
   - Would eliminate potential state confusion during concurrent access

2. **Add finalization timeout**
   - Currently no timeout on finalization worker
   - Long-running PR creation could block indefinitely
   - Suggestion: Add timeout with fallback to "error" state

3. **Improve thread cleanup**
   - _finalization_threads dict grows indefinitely
   - Consider periodic cleanup of completed threads
   - Or use weak references

4. **Add finalization metrics**
   - Track finalization duration by reason
   - Track failure rates
   - Would help identify performance issues

5. **Consolidate cleanup logic**
   - Cleanup is called from 3 different places
   - Consider single cleanup coordinator
   - Would reduce chance of missed cleanup

6. **Add finalization queue**
   - Currently one thread per task
   - Could use thread pool for better resource management
   - Would prevent resource exhaustion with many tasks

## Testing Checklist

- [ ] Task completes normally → finalization runs
- [ ] User stops task → finalization runs
- [ ] User kills task → finalization runs
- [ ] App restart with unfinalized tasks → startup_reconcile runs
- [ ] Multiple finalization triggers → only one finalization runs
- [ ] Interactive task completion → finalization_state set to "done"
- [ ] PR creation success → gh_pr_url updated
- [ ] PR creation failure → error logged, state = "error"
- [ ] Artifact collection timeout → graceful handling
- [ ] Workspace cleanup success → logs show "cleaned"
- [ ] Workspace cleanup failure → error logged but finalization completes
- [ ] Recovery tick with finalization in progress → no duplicate work
- [ ] finalization_state persistence → survives app restart
