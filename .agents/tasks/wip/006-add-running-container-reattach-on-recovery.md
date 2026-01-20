# Task 006: Add Running Container Reattach Support on Recovery

## Objective
When app restarts and interactive container is still running, resume monitoring and enable reattach.

## Context
- If user closes app while interactive task is running, container continues
- On restart, app should detect running container and allow user to reattach
- Need to tail logs and show UI affordance for reattach

## Requirements
1. If completion marker doesn't exist but container exists and is running:
   - Set task status to `running`
   - Start log tail: `docker logs -f <container_name>`
   - Enable UI "Attach" or "Reattach" button
2. Log tail should continue until container exits
3. When container exits, recovery should detect it and queue finalization

## Location to Change
- File: `agents_runner/ui/main_window_task_recovery.py`
- Function: `_reconcile_tasks_after_restart` and `_ensure_recovery_log_tail`

## Acceptance Criteria
- [ ] Recovery detects running interactive container with `docker inspect`
- [ ] Sets task status to `running` if container is active
- [ ] Starts `docker logs -f` tail for running container
- [ ] Logs appear in UI
- [ ] UI shows "Attach" or "Reattach" button/option
- [ ] Recovery continues monitoring until container exits

## Notes
- Reuse existing log tail mechanism: `_ensure_recovery_log_tail()`
- Check container state with: `docker inspect --format='{{.State.Status}}' <name>`
- Depends on task 003 (detached container launch)
