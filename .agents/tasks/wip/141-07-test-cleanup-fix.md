# Task: Test Staging Cleanup Robustness

**Issue:** #141  
**Target File:** `agents_runner/artifacts.py` (verification)  
**Type:** Testing  
**Depends On:** Task 141-04

## Objective
Verify that the staging directory cleanup fix handles all filesystem structures correctly.

## Task
1. Run `uv run main.py` and execute multiple tasks with artifact generation
2. Monitor logs for any `Staging cleanup failed` errors
3. Test edge cases:
   - Tasks that create nested directories in staging
   - Tasks that create many files
   - Tasks that fail during artifact generation
   - Tasks stopped/killed mid-execution
4. Verify staging directories are cleaned up properly after each task
5. Check `~/.midoriai/agents-runner/artifacts/` for leftover staging directories
6. Remove any temporary debug logging added in task 141-02

## Acceptance Criteria
- [ ] No `Directory not empty` errors during normal operation
- [ ] No errors during edge case testing
- [ ] All staging directories cleaned up after task completion
- [ ] Artifact encryption/collection still works correctly
- [ ] Debug logging removed

## Rationale
The fix must handle real-world scenarios including nested directories, race conditions, and error cases. Confirming staging directories are cleaned up prevents disk space leaks.
