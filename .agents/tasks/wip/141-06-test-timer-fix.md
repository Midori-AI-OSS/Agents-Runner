# Task: Test Qt Timer Thread Affinity Fix

**Issue:** #141  
**Target File:** `agents_runner/docker/artifact_file_watcher.py` (verification)  
**Type:** Testing  
**Depends On:** Task 141-03

## Objective
Verify that the ArtifactFileWatcher thread affinity fix eliminates cross-thread timer warnings.

## Task
1. Run `uv run main.py` and execute multiple tasks with artifact generation
2. Monitor stderr/console for any Qt timer warnings
3. Test edge cases:
   - Tasks that fail/timeout during execution
   - Rapid task start/stop cycles
   - Tasks with no artifacts
   - Tasks with many artifacts
4. Verify no new warnings, crashes, or hangs introduced
5. Remove any temporary debug logging added in task 141-01

## Acceptance Criteria
- [ ] No `QObject::killTimer` or `QObject::startTimer` warnings during normal operation
- [ ] No warnings during edge case testing
- [ ] File watching functionality works correctly
- [ ] Debug logging removed

## Rationale
Comprehensive testing ensures the fix works in all scenarios and doesn't introduce new issues. The absence of warnings confirms proper thread affinity.
