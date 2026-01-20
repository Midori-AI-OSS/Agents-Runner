# Task 009: Add Docker Wait Exit Code Backup

## Objective
Add a backup mechanism to capture container exit code using `docker wait` when app is alive.

## Context
- Completion marker writing uses a shell trap which can be bypassed by SIGKILL
- If app is running when container exits, it can capture exit code directly with `docker wait`
- This provides redundancy for completion marker

## Requirements
1. When interactive container is running, start a `docker wait <container_name>` process
2. When wait completes, capture the exit code
3. If completion marker doesn't exist, write it using the wait exit code
4. If marker exists, validate it matches wait exit code (log warning if mismatch)

## Location to Change
- File: `agents_runner/ui/main_window_tasks_interactive_docker.py`
- Function: `launch_docker_terminal_task` or container lifecycle management
- Add as part of the container monitoring logic after container is launched
- Alternative: Create a new background thread/monitor in the interactive task orchestration

## Acceptance Criteria
- [ ] `docker wait` process started when interactive container launches
- [ ] Exit code captured when wait completes
- [ ] Writes completion marker if missing
- [ ] Validates marker if it already exists
- [ ] Logs warning if marker exit_code doesn't match wait exit_code

## Notes
- Run `docker wait` in background thread or async
- Command: `docker wait <container_name>` returns exit code
- This ensures exit code is captured even if trap fails
- Lower priority than other tasks, implement after basic flow works
