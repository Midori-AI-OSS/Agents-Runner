# Task: Review and optimize recovery_tick interval

## Problem
Recovery_tick runs every 5 seconds unconditionally. For applications with many completed tasks or mostly stable state, this may be too frequent. Note: Implementing Task 03 (stable task tracking) significantly reduces work per tick and may make interval changes unnecessary.

## Context
Code comments (lines 139-143) contain rationale for 5-second interval and reference missing implementation document `.agents/implementation/recovery-tick-timing-analysis.md` (file does not exist).

## Location
File: `agents_runner/ui/main_window.py`
Lines: 138-146 (QTimer setup)

## Required Analysis
Review whether 5-second interval is optimal:

**Current setup:**
```python
self._recovery_ticker = QTimer(self)
self._recovery_ticker.setInterval(5000)  # 5 seconds
self._recovery_ticker.timeout.connect(self._tick_recovery)
self._recovery_ticker.start()
```

## Considerations
1. **Safety vs Performance:** Balance between catching missed events quickly vs CPU/log overhead
2. **Task patterns:** Most tasks complete cleanly via event-driven finalization
3. **Recovery is safety net:** Only needed when events are missed
4. **Dynamic interval:** Consider adaptive interval (5s when active tasks, 30s when all stable)

## Recommended Options
- **Option A (Preferred):** Keep 5s but implement Task 03 (stable task tracking) to reduce work per tick, then re-evaluate
- **Option B:** Increase to 10-15s (recovery is edge case, not primary path)
- **Option C:** Adaptive interval based on active task count
- **Option D:** Only run recovery when tasks exist that need checking
- **Option E:** Create or remove reference to `.agents/implementation/recovery-tick-timing-analysis.md`

## Implementation Priority
**Recommendation:** Implement Task 03 first, then re-evaluate if interval adjustment is still needed. Task 03 addresses the root cause (repeated processing) while keeping the safety net responsive.

## Acceptance Criteria
- Decision documented on chosen approach
- If interval changed, verify edge cases still caught (container state changes, missed events)
- Performance improved without sacrificing reliability
- Referenced implementation document either created or reference removed from code
- Evaluation done AFTER Task 03 implementation for accurate impact assessment

## Testing
1. Simulate missed events (kill container externally, force restart)
2. Verify recovery still catches and finalizes tasks
3. Measure CPU/log impact before and after change
