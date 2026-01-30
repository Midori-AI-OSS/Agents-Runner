# Task 008: Review Startup Reconciliation Logic

## Objective
Ensure that `_reconcile_tasks_after_restart()` only runs once at startup and doesn't interfere with normal finalization.

## Scope
- Review `_reconcile_tasks_after_restart()` implementation in `agents_runner/ui/main_window_task_recovery.py`
- Verify it only runs once at app startup (check for flags or guards)
- Check if it properly distinguishes between truly incomplete tasks vs just-completed tasks
- Ensure it doesn't duplicate work that recovery_tick will do
- Review how it determines which tasks need finalization

## Acceptance Criteria
- Startup reconciliation runs exactly once at app start (verify with flag/guard mechanism)
- It correctly identifies tasks that need finalization (define criteria)
- It doesn't queue duplicate finalization for tasks (add guard checks if needed)
- Clear distinction in code and logs between "startup_reconcile" and "recovery_tick" reasons
- Document in `.agents/implementation/` when each path is used and why both are needed

## Related Issues
- #148: Finalize Memes with `recovery_tick`
- #155: More memes with `recovery_tick`

## Dependencies
- Task 001

## Estimated Effort
Small (1 hour)
