# Task 009: Add Debug Logging for Finalization Events

## Objective
Add comprehensive logging to help diagnose finalization issues in production.

## Scope
- Add logging when finalization is queued (with reason and current state)
- Add logging when finalization is skipped (with reason and current state)
- Log finalization state transitions (None → pending → running → done/error)
- Log thread lifecycle (start, alive check, completion)
- Use consistent log format matching existing patterns in the codebase
- Files to modify: `agents_runner/ui/main_window_task_recovery.py`, `agents_runner/ui/main_window_task_events.py`, `agents_runner/ui/main_window_tasks_interactive_finalize.py`

## Acceptance Criteria
- All finalization decision points have clear log messages (list at least 5 key decision points)
- Logs include task_id, reason, current state, and action taken in format: "Task <id>: <action> finalization (reason=<reason>, state=<state>)"
- Logs use existing logging functions for consistency (check codebase for format_log() or similar)
- Log level is appropriate: INFO for normal flow, DEBUG for verbose details, WARNING for skips that might indicate issues
- Logs are helpful for debugging but not overly verbose (aim for 3-5 log lines per finalization attempt)
- Test the logging by running a task and reviewing the output

## Related Issues
- #148: Finalize Memes with `recovery_tick`
- #155: More memes with `recovery_tick`

## Dependencies
- Task 002

## Estimated Effort
Small (1 hour)
