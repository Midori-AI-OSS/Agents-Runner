# Task 005: Add Completion Marker Detection to Recovery

## Objective
Teach restart recovery to check for the interactive completion marker and finalize accordingly.

## Context
- When app restarts, interactive tasks need special recovery logic
- If completion marker exists in staging, the task completed (even if container is gone)
- Recovery should read the marker and set task status/exit_code appropriately

## Requirements
1. On startup, for each interactive task not finalized, check for completion marker
2. Marker path: `~/.midoriai/agents-runner/artifacts/<task_id>/staging/interactive-exit.json`
3. If marker exists:
   - Parse JSON and extract exit_code, finished_at
   - Set task status to `done` (exit_code==0) or `failed` (exit_code!=0)
   - Set task.finished_at from marker
   - Queue task for finalization
4. If marker doesn't exist and container doesn't exist:
   - Mark task as `unknown` or `failed (unrecoverable)`

## Location to Change
- File: `agents_runner/ui/main_window_task_recovery.py`
- Function: `_reconcile_tasks_after_restart` or helper function

## Acceptance Criteria
- [ ] Recovery checks for completion marker file before docker inspect
- [ ] Successfully parses marker JSON
- [ ] Sets task status based on exit_code from marker
- [ ] Sets task.finished_at from marker timestamp
- [ ] Queues task for finalization if marker indicates completion
- [ ] Handles missing marker gracefully (doesn't crash)

## Notes
- Check for marker existence with `os.path.exists()`
- Use `json.load()` to parse marker content
- This fixes the bug where UI restart causes task to be stuck in "running/unknown"
- Depends on task 001 (marker writing must be working)
