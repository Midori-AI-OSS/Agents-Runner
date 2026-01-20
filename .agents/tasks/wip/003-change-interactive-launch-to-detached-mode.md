# Task 003: Change Interactive Container Launch to Detached Mode

## Objective
Launch interactive container in detached mode with app ownership, instead of terminal script ownership.

## Context
- Currently, a host shell script runs `docker run -it` and owns the container lifecycle
- This causes issues with restart recovery and finalization
- Solution: App launches container detached with `-dit`, then terminal attaches to it

## Requirements
1. App code should run `docker run --rm -dit --name <container_name> ...` directly
2. Container should start with TTY allocated (`-t`) for attach compatibility
3. Container should be detached (`-d`) so app owns lifecycle, not terminal
4. Container name should follow convention: `agents-runner-tui-it-<task_id>`
5. Remove the old "host shell script runs docker run" approach

## Location to Change
- File: `agents_runner/ui/main_window_tasks_interactive_docker.py`
- Replace `_build_host_shell_script` approach with direct docker run

## Acceptance Criteria
- [ ] App directly executes `docker run --rm -dit` (not via host script)
- [ ] Container starts in detached mode
- [ ] Container has stable name: `agents-runner-tui-it-<task_id>`
- [ ] App records container name/ID in Task payload
- [ ] Terminal script no longer runs `docker run`

## Notes
- Use `--rm` to keep auto-remove behavior
- Use `-d` for detached, `-i` for interactive stdin, `-t` for TTY
- This enables task 004 (terminal attach) to work properly
