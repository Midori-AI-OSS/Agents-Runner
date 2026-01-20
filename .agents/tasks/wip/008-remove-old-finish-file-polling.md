# Task 008: Remove Old Finish File Polling Mechanism

## Objective
Clean up the old plaintext finish file polling code now that we use the JSON completion marker.

## Context
- Old implementation wrote `~/.midoriai/agents-runner/interactive-finish-<task_id>.txt`
- Old implementation polled for this file in `_start_interactive_finish_watch`
- New design uses JSON completion marker in staging directory instead
- Old code should be removed to avoid confusion and maintenance burden

## Requirements
1. Remove finish file polling code
2. Remove finish file writing code from host shell script
3. Clean up related watchers and threads
4. Ensure no code depends on the old finish file path

## Location to Change
- File: `agents_runner/ui/main_window_tasks_interactive.py`
- Function: `_start_interactive_finish_watch` (likely remove entirely)
- File: `agents_runner/ui/main_window_tasks_interactive_docker.py`
- Function: `_build_host_shell_script` (remove finish file write)

## Acceptance Criteria
- [ ] `_start_interactive_finish_watch` function removed or disabled
- [ ] No code writes to `interactive-finish-<task_id>.txt`
- [ ] No code polls for plaintext finish file
- [ ] No watcher threads for old finish file
- [ ] Code successfully uses new JSON marker instead

## Notes
- This is cleanup after tasks 001 and 005 are working
- Search codebase for "interactive-finish" to find all references
- May need to update function that calls `_start_interactive_finish_watch`
