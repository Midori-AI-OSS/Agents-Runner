# Recovery Tick Timing Strategy Analysis

## Executive Summary

This document analyzes the current 1-second recovery tick interval and proposes alternative timing strategies for the task finalization recovery system. The analysis evaluates trade-offs between quick recovery and system efficiency.

## Current Implementation

### Recovery Tick Configuration
**Location**: `agents_runner/ui/main_window.py:138-141`
```python
self._recovery_ticker = QTimer(self)
self._recovery_ticker.setInterval(1000)  # 1 second
self._recovery_ticker.timeout.connect(self._tick_recovery)
self._recovery_ticker.start()
```

### What Recovery Tick Does
**Location**: `agents_runner/ui/main_window_task_recovery.py:27-81`

Every 1 second, the recovery tick:
1. Iterates through ALL tasks in `self._tasks`
2. For each task, calls `_tick_recovery_task(task)`
3. Which performs:
   - Early exit if `finalization_state == "done"`
   - Container state sync for active/unknown tasks
   - UI updates if state changed
   - Log tail management for active tasks
   - Finalization queueing for completed tasks needing finalization

### Current Safeguards (Added in Recent Updates)
**Location**: `agents_runner/ui/main_window_task_recovery.py:46-81`

The code now has **SYNCHRONIZATION GUARD 1** and **SYNCHRONIZATION GUARD 2**:
1. Checks if `finalization_state` is already "pending" or "running" (lines 50-61)
2. Checks if finalization thread already exists and is alive (lines 66-79)

These prevent duplicate finalization work even with the frequent 1-second ticks.

## Analysis of 1-Second Interval

### Pros (Quick Recovery)

#### 1. Fast Failure Detection
- **Benefit**: Detects container crashes/exits within 1 second
- **Use Case**: Task container unexpectedly exits while app is running
- **Impact**: User sees status update almost immediately

#### 2. Quick Finalization After Completion
- **Benefit**: Tasks that complete without triggering `_on_task_done()` get finalized within 1 second
- **Use Case**: Bridge fails to emit done signal, or signal gets lost
- **Impact**: System self-heals quickly without user intervention

#### 3. Responsive Log Tailing
- **Benefit**: Recovery log tail starts quickly for tasks missing a bridge
- **Use Case**: Task started before bridge established, or bridge disconnected
- **Impact**: User gets log output quickly even when bridge is unavailable

#### 4. Predictable Behavior
- **Benefit**: Consistent 1-second rhythm makes behavior predictable
- **Use Case**: Debugging and testing
- **Impact**: Easier to reason about timing-related issues

### Cons (Frequent Checks)

#### 1. CPU Usage for Idle Tasks
- **Cost**: Checks all tasks every second, even when nothing is happening
- **Scale**: With N tasks, performs N checks per second
- **Example**: 10 completed tasks = 10 finalization_state checks/second
- **Impact**: Minimal (simple dictionary lookups and string comparisons)

#### 2. Potential Log Spam (Mitigated)
- **Concern**: Could generate excessive log entries
- **Mitigation**: Current code only logs when taking action (lines 52-80)
- **Impact**: LOW - No log spam in normal operation

#### 3. Redundant Work for Normal Completion
- **Issue**: Task completes via `_on_task_done()`, but recovery_tick also checks it
- **Mitigation**: Synchronization guards prevent duplicate finalization
- **Impact**: LOW - Guards are efficient (just state checks)

#### 4. No Backoff Strategy
- **Concern**: Checks continue at same rate regardless of task state stability
- **Example**: Task finalized 1 hour ago still checked every second
- **Impact**: LOW - Early exit on "done" state is cheap

## Best Practices Research

### Industry Patterns for Recovery/Reconciliation

#### 1. Kubernetes Reconciliation Loop
**Pattern**: Controller pattern with configurable intervals
- Default sync period: 10-60 seconds
- Immediate reconciliation on events
- Exponential backoff on errors
- **Rationale**: Balance responsiveness with cluster load

#### 2. Database Replication
**Pattern**: Heartbeat + change-based triggers
- Heartbeat interval: 1-5 seconds
- Change-based: Immediate on transaction log entry
- **Rationale**: Fast detection of failures, efficient for idle periods

#### 3. Distributed Systems (Consul, etcd)
**Pattern**: Multi-tier timing
- Health checks: 10-30 seconds
- Leader election: 1-3 seconds
- Client heartbeat: 1-5 seconds
- **Rationale**: Different timing for different purposes

#### 4. Cloud Provider APIs (AWS, Azure)
**Pattern**: Exponential backoff with jitter
- Initial retry: 1 second
- Max retry: 60 seconds
- **Rationale**: Reduce thundering herd, respect rate limits

### Synthesis: Patterns Applicable to Recovery Tick

1. **Event-Driven + Periodic Polling Hybrid** ✅ Already implemented
   - Events: `_on_task_done()`, `_on_task_container_action()`
   - Polling: Recovery tick

2. **State-Based Intervals** ⚠️ Not implemented
   - Different intervals for different states
   - Example: Active tasks check every 1s, completed every 30s

3. **Exponential Backoff** ⚠️ Not implemented
   - Check more frequently when task state is changing
   - Back off when stable

4. **Immediate + Delayed** ✅ Partially implemented
   - Immediate: Event-driven finalization
   - Delayed: Recovery tick as safety net

## Alternative Timing Strategies

### Strategy 1: Increase Base Interval (Conservative)
**Change**: Set recovery tick to 5 seconds instead of 1 second

```python
self._recovery_ticker.setInterval(5000)  # 5 seconds
```

**Pros**:
- Reduces check frequency by 80%
- Still catches failures relatively quickly
- Maintains simple, predictable behavior

**Cons**:
- Container failure detection: 1s → 5s delay
- Log tail startup: 1s → 5s delay
- Less responsive for edge cases

**Recommendation**: ✅ **Good compromise**

### Strategy 2: Startup-Only Recovery (Aggressive)
**Change**: Only run recovery during startup reconciliation, disable ongoing ticker

```python
# In __init__, remove ticker start:
# self._recovery_ticker.start()  # REMOVED

# Keep startup reconciliation:
# _reconcile_tasks_after_restart() still runs
```

**Pros**:
- Eliminates ongoing overhead completely
- Focuses recovery on actual recovery scenarios (app restart)
- Event-driven paths handle normal operation

**Cons**:
- ❌ No safety net for missed events during runtime
- ❌ No container state sync for running tasks
- ❌ No recovery log tail management
- ❌ Breaking change: relies 100% on event-driven paths

**Recommendation**: ❌ **Too risky** - removes important safety nets

### Strategy 3: State-Based Adaptive Intervals (Sophisticated)
**Change**: Different intervals based on task state

```python
def _tick_recovery_task(self, task: Task) -> None:
    # Check how recently task state changed
    time_since_last_change = time.time() - task.last_status_change_time
    
    # Skip if task is stable and recently checked
    if task.finalization_state == "done":
        # Completed tasks: check every 60 seconds
        if time_since_last_change < 60:
            return
    elif task.is_active():
        # Active tasks: check every 2 seconds
        if time.time() - task.last_recovery_check < 2:
            return
    else:
        # Transitioning tasks: check every 1 second
        if time.time() - task.last_recovery_check < 1:
            return
    
    task.last_recovery_check = time.time()
    # ... existing logic
```

**Pros**:
- Optimizes check frequency based on actual need
- Active tasks get frequent checks
- Stable tasks get infrequent checks
- Maintains safety net for all states

**Cons**:
- Requires adding timestamp tracking to Task model
- More complex logic to test and maintain
- May introduce subtle timing bugs

**Recommendation**: ⚠️ **Interesting but complex** - consider for future optimization

### Strategy 4: Add Last-Finalization-Attempt Timestamp (Targeted)
**Change**: Track when finalization was last attempted to prevent rapid re-checks

```python
# In Task model:
last_finalization_attempt: float = 0.0  # timestamp

# In _tick_recovery_task:
def _tick_recovery_task(self, task: Task) -> None:
    if (task.finalization_state or "").lower() == "done":
        return
    
    # NEW: Skip if finalization was recently attempted
    if task.last_finalization_attempt > 0:
        time_since_attempt = time.time() - task.last_finalization_attempt
        if time_since_attempt < 10.0:  # 10 second cooldown
            return
    
    # ... existing logic
    
# In _queue_task_finalization:
def _queue_task_finalization(self, task_id: str, *, reason: str) -> None:
    # ... existing guards ...
    
    # NEW: Record attempt timestamp
    task.last_finalization_attempt = time.time()
    
    # ... start thread
```

**Pros**:
- Prevents rapid re-attempts on transient issues
- Simple to implement and understand
- Maintains 1-second base interval for other checks
- No change to ticker interval

**Cons**:
- Adds field to Task model
- Requires persistence consideration
- 10-second cooldown might delay legitimate retries

**Recommendation**: ✅ **Good targeted fix** for finalization-specific concerns

### Strategy 5: Hybrid Approach (Recommended)
**Change**: Combine multiple strategies

```python
# 1. Increase base interval to 5 seconds
self._recovery_ticker.setInterval(5000)

# 2. Add synchronization guard for finalization_state "pending"/"running"
#    (ALREADY IMPLEMENTED in lines 50-79)

# 3. Optional: Add last_finalization_attempt timestamp for extra safety
```

**Pros**:
- Reduces check frequency by 80% (1s → 5s)
- Maintains all safety nets (state sync, log tail, finalization)
- Existing guards prevent duplicate work
- Simple change with low risk

**Cons**:
- Slightly slower failure detection (5s vs 1s)
- Still checks all tasks every 5 seconds

**Recommendation**: ✅ **RECOMMENDED** - Best balance of simplicity and efficiency

## Recommendation Summary

### Immediate Action (Low Risk, High Reward)
**Increase recovery tick interval from 1 second to 5 seconds**

**Implementation**:
```python
# File: agents_runner/ui/main_window.py
# Line: 139

# Change from:
self._recovery_ticker.setInterval(1000)

# To:
self._recovery_ticker.setInterval(5000)
```

**Rationale**:
- Current synchronization guards (lines 50-79) already prevent duplicate finalization
- 5-second interval is still fast enough for recovery scenarios
- Reduces check frequency by 80%
- Minimal code change, easy to revert if issues arise
- Aligns with industry best practices (Kubernetes: 10-60s, distributed systems: 5-30s)

### Future Optimization (If Needed)
If 5 seconds proves insufficient or overhead is still a concern:

**Option A**: Add last_finalization_attempt timestamp (Strategy 4)
- Targeted fix for finalization-specific concerns
- Maintains fast interval for state sync and log tail

**Option B**: Implement state-based intervals (Strategy 3)
- Maximum efficiency
- More complex, requires thorough testing

### What NOT to Do
❌ **Do not disable recovery tick entirely** (Strategy 2)
- Removes critical safety nets
- Breaks container state sync
- Breaks recovery log tail
- Too risky

## Trade-Off Analysis

| Strategy | Check Frequency | Recovery Speed | Safety Net | Complexity | Recommendation |
|----------|----------------|----------------|------------|------------|----------------|
| Current (1s) | 1/s per task | 1s | Full | Low | ✅ Works but could be optimized |
| 5s Interval | 0.2/s per task | 5s | Full | Low | ✅✅ **RECOMMENDED** |
| Startup-Only | 0/s (runtime) | N/A | Partial | Low | ❌ Too risky |
| Adaptive | Variable | 1-60s | Full | High | ⚠️ Future consideration |
| + Timestamp | 1/s per task | 1s | Full | Medium | ✅ Good targeted fix |
| Hybrid | 0.2/s per task | 5s | Full | Low | ✅✅ **RECOMMENDED** |

## Implementation Considerations

### 1. Testing Requirements
After changing interval, verify:
- [ ] Container failure detection still works
- [ ] Recovery log tail starts promptly
- [ ] Finalization triggers appropriately
- [ ] No regression in edge cases (issues #148, #155)
- [ ] UI updates remain responsive

### 2. Monitoring
Add metrics to track:
- Recovery tick execution time
- Number of tasks checked per tick
- Number of actions taken per tick
- Finalization queue depth

### 3. Rollback Plan
If 5-second interval causes issues:
1. Revert to 1 second immediately
2. Investigate specific failure case
3. Consider targeted fix (Strategy 4) instead

### 4. Documentation Updates
Update these files:
- `.agents/implementation/recovery-tick-behavior.md` - Document new interval
- `.agents/implementation/task-finalization-flow.md` - Update timing info
- Code comments in `main_window.py` - Explain interval choice

## Conclusion

**The current 1-second interval is functional but more frequent than necessary.**

The recently added synchronization guards (GUARD 1 and GUARD 2) already prevent duplicate finalization work, making the frequent checks redundant in normal operation. The recovery tick's primary value is as a **safety net for edge cases**, not as a primary finalization mechanism.

**Recommendation: Increase interval to 5 seconds** (Strategy 5 - Hybrid Approach)

This provides:
- ✅ 80% reduction in check frequency
- ✅ Maintains all safety nets
- ✅ Still fast enough for recovery scenarios
- ✅ Aligns with industry best practices
- ✅ Simple change, low risk
- ✅ Easy to revert if needed

The 5-second interval strikes the right balance between responsiveness and efficiency, especially given that:
1. Event-driven paths (`_on_task_done()`, `_on_task_container_action()`) handle normal operation immediately
2. Recovery tick is a backup mechanism for edge cases
3. Most recovery scenarios (app restart, missed events) don't require sub-second response
4. Container state sync and log tail management benefit from checks, but don't need 1-second granularity

## References

- Issue #148: Finalize Memes with `recovery_tick`
- Issue #155: More memes with `recovery_tick`
- `.agents/implementation/recovery-tick-behavior.md`
- `.agents/implementation/task-finalization-flow.md`
- `agents_runner/ui/main_window.py:138-141`
- `agents_runner/ui/main_window_task_recovery.py:27-81`
