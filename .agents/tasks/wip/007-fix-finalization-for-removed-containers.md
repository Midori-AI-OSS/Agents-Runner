# Task 007: Fix Finalization to Work Without Container

## Objective
Update finalization to collect artifacts from host staging directory instead of requiring container to exist.

## Context
- Interactive containers are auto-removed on exit
- Current finalization tries to `docker cp` from container, which fails if container is gone
- Solution: Collect artifacts from host staging directory which persists after removal

## Requirements
1. When finalizing interactive tasks, check if container exists
2. If container is gone, collect artifacts from host staging path instead of `docker cp`
3. Host staging path: `~/.midoriai/agents-runner/artifacts/<task_id>/staging/`
4. Encryption and PR prompts should still work using host-collected artifacts

## Location to Change
- File: `agents_runner/ui/main_window_task_recovery.py`
- Function: `_finalize_task_worker`

## Acceptance Criteria
- [ ] Finalization checks if container exists before attempting docker cp
- [ ] If container is missing, collects from host staging directory
- [ ] Artifact encryption works with host-sourced files
- [ ] PR prompts work with host-sourced files
- [ ] Finalization completes successfully even when container is auto-removed
- [ ] Sets `finalization_state="done"` when complete

## Notes
- Use `docker inspect` to check container existence (returns error if missing)
- Fallback to host staging path: `~/.midoriai/agents-runner/artifacts/<task_id>/staging/`
- This prevents stuck finalization that errors on missing container
- Depends on task 002 (staging directory mount)
