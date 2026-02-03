# CONT-002: Verify Container Controls After Fix

**Priority:** Medium  
**Status:** Blocked (waiting for CONT-001)  
**Type:** Verification / Testing  
**Estimated Complexity:** Small

## Problem

After fixing the container ID propagation issue (CONT-001), we need to verify that all container controls work correctly for both non-interactive and interactive runs.

## Dependencies

- **Blocked by:** CONT-001 (must be completed first)

## Acceptance Criteria

1. All container controls work for non-interactive agent runs:
   - Freeze button pauses the container
   - Unfreeze button resumes a paused container
   - Stop button gracefully stops the container
   - Kill button force-kills the container
   
2. All container controls work for interactive runs (regression test)

3. Container controls are correctly enabled/disabled based on task state:
   - Enabled when task is running and has a container
   - Disabled when task is paused (except Unfreeze)
   - Disabled when task is in terminal state (cancelled, killed, completed)

4. UI updates correctly show container state changes

## Verification Steps

### Non-Interactive Run Tests

1. **Start a new non-interactive agent task**
   - Verify container ID appears in task details immediately
   - Verify Freeze, Stop, and Kill buttons are enabled
   - Verify Unfreeze button is disabled

2. **Test Freeze button**
   - Click Freeze while task is running
   - Verify task status changes to "paused"
   - Verify container is actually paused (check with `docker ps`)
   - Verify Freeze button becomes disabled
   - Verify Unfreeze button becomes enabled

3. **Test Unfreeze button**
   - Click Unfreeze on a paused task
   - Verify task status changes back to "running"
   - Verify container resumes execution
   - Verify Unfreeze button becomes disabled
   - Verify Freeze button becomes enabled

4. **Test Stop button**
   - Start a new task
   - Click Stop button
   - Verify task stops gracefully
   - Verify task status changes to appropriate terminal state
   - Verify all container control buttons become disabled

5. **Test Kill button**
   - Start a new task
   - Click Kill button
   - Verify container is force-killed immediately
   - Verify task status changes to "killed"
   - Verify all container control buttons become disabled

### Interactive Run Tests (Regression)

6. **Repeat tests 1-5 for interactive agent runs**
   - Interactive runs use container IDs starting with `agents-runner-tui-it-`
   - Verify all controls still work as expected

### Edge Cases

7. **Test state synchronization**
   - Pause a container via Docker CLI (`docker pause <container_id>`)
   - Verify UI updates to show "paused" state
   - Verify button states update correctly

8. **Test rapid state changes**
   - Click Freeze, then immediately click Unfreeze
   - Verify no race conditions or UI glitches

9. **Test after task completion**
   - Let a task complete normally
   - Verify container ID is still visible
   - Verify all control buttons are disabled

## Files to Check

- `agents_runner/ui/pages/task_details.py` - Button enable/disable logic
- `agents_runner/ui/main_window_task_events.py` - Container action handlers
- `agents_runner/ui/task_model.py` - Task state model

## Success Criteria

- All verification steps pass without issues
- No regressions in interactive run behavior
- Container controls respond promptly to user actions
- UI state accurately reflects container state

## Notes

- This is a verification-only task - do not modify code unless a new issue is discovered
- If new issues are found during testing, create separate task files for them
- Document any unexpected behavior in test results
- Consider taking screenshots or recording a video of the working controls for documentation
