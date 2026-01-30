# Task Breakdown Summary - Issues #148 and #155

## Problem Statement
Both issues report that finalization is running multiple times due to `recovery_tick`. The logs show finalization happening twice:
1. Once with `reason=task_done` (expected)
2. Again with `reason=recovery_tick` (duplicate)

This causes issues including:
- Failed PR uploads (issue #162)
- Potential artifact collection problems
- Unnecessary resource usage

## Root Cause
The recovery ticker (`QTimer`) runs every 1 second and calls `_tick_recovery()`, which iterates through all tasks and checks if they need finalization. When a task completes, both the task completion handler AND the recovery ticker try to queue finalization.

## Task Breakdown

### Investigation Tasks (2 tasks)
- **Task 001**: Investigate recovery tick behavior and when it should/shouldn't trigger
- **Task 002**: Trace complete finalization flow and document state machine

### Core Fix Tasks (3 tasks)
- **Task 003**: Add guards to prevent recovery_tick from duplicating finalization
- **Task 004**: Review and fix task_done event handler
- **Task 005**: Strengthen deduplication logic in _queue_task_finalization()

### Optimization Tasks (2 tasks)
- **Task 006**: Consider recovery tick timing strategy (frequency, cooldown)
- **Task 008**: Review startup reconciliation logic

### Verification Tasks (2 tasks)
- **Task 007**: Test finalization in all scenarios
- **Task 010**: Verify PR creation works after fix

### Documentation Tasks (2 tasks)
- **Task 009**: Add debug logging for finalization events
- **Task 011**: Document finalization architecture

## Priority Order

### High Priority (Must Fix)
1. Task 001 - Investigation (foundation)
2. Task 002 - Flow tracing (foundation)
3. Task 003 - Fix duplicate guard (core fix)
4. Task 005 - Deduplication logic (core fix)

### Medium Priority (Should Fix)
5. Task 004 - Task done handler review
6. Task 008 - Startup reconciliation
7. Task 007 - Testing scenarios

### Nice to Have
8. Task 006 - Timing strategy
9. Task 009 - Debug logging
10. Task 010 - PR verification
11. Task 011 - Documentation

## Key Files to Modify
- `agents_runner/ui/main_window_task_recovery.py` - Recovery tick logic
- `agents_runner/ui/main_window_task_events.py` - Task done handler
- `agents_runner/ui/main_window.py` - Timer setup

## Success Criteria
- Finalization runs exactly once per task completion
- No duplicate "finalization running" log messages
- PR creation works reliably (issue #162 resolved)
- Artifacts collected correctly
- Clean, understandable logs
