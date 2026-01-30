# Task 007: Test Finalization in Various Scenarios

## Objective
Verify that finalization works correctly and only runs once in all scenarios.

## Scope
## Scope
Test the following scenarios with the fixes in place:
- Normal task completion (exit code 0)
- Task failure (non-zero exit code)
- User cancellation (stop button)
- User kill (kill button)
- Task discard from UI
- App restart with incomplete tasks
- App restart with completed but not-finalized tasks
- Multiple tasks completing in rapid succession (run 3+ tasks concurrently)

For each scenario, capture logs and verify behavior.

## Acceptance Criteria
- Finalization runs exactly once per task in all 8 scenarios tested
- No "finalization running (reason=recovery_tick)" messages AFTER task_done finalization in logs
- PR creation works correctly in all applicable scenarios (save test results)
- Artifact collection happens once and completes successfully (verify files exist)
- Clean logs without duplicate finalization messages (provide log excerpts)
- Create a test report document in `.agents/implementation/` summarizing results

## Related Issues
- #148: Finalize Memes with `recovery_tick`
- #155: More memes with `recovery_tick`

## Dependencies
- Task 003
- Task 005

## Estimated Effort
Medium (3-4 hours)
