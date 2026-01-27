# Task: Fix Interactive Task Status Display (Issue #151)

## Issue Reference
- GitHub Issue: #151
- Title: "Interactive Tasks Error"
- Problem: Interactive tasks show "fail" status while they are running, instead of showing "running" status

## Current Behavior
When an interactive task is launched, the UI displays a "Failed" status indicator even though the task is actively running.

## Root Cause Analysis Required
Investigate status synchronization for interactive tasks:
1. Check `agents_runner/ui/main_window_persistence.py` lines 40-98 where `_sync_docker_task_state()` updates task status from Docker container state
2. Review how interactive task status is set in `agents_runner/ui/main_window_tasks_interactive_docker.py` line 285 where status is set to "running"
3. Investigate if Docker container inspection is incorrectly overriding the "running" status for interactive tasks
4. Check if the status mapping at line 92 in `main_window_persistence.py` is being applied to interactive tasks when it shouldn't be

## Expected Fix
Interactive tasks that are actively running should display "Running" status in the UI, not "Failed".

## How to Reproduce
1. Launch the Agents Runner GUI: `uv run main.py`
2. Create or select an environment
3. Start an interactive task from the UI
4. Observe the task status indicator - it shows "Failed" (red X) instead of "Running"

## How to Verify
1. Launch the Agents Runner GUI: `sudo uv run main.py` (sudo required for docker socket access)
2. Start an interactive task
3. Confirm the status shows "Running" with appropriate visual indicator (not "Failed")
4. Wait for the interactive task to complete naturally
5. Verify final status correctly shows "Done" or "Failed" based on exit code

## Files to Investigate
- `agents_runner/ui/main_window_persistence.py` - Docker state sync logic
- `agents_runner/ui/main_window_tasks_interactive_docker.py` - Interactive task status setting
- `agents_runner/ui/task_model.py` - Task status methods (`is_failed()`, `is_active()`)
- `agents_runner/ui/pages/dashboard_row.py` - Status display logic

## Acceptance Criteria
- [ ] Interactive tasks show "Running" status while container is active
- [ ] Interactive tasks correctly transition to "Done" or "Failed" on completion
- [ ] Non-interactive tasks are not affected by the fix
- [ ] Recovery tick does not incorrectly change interactive task status
