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
- [x] App directly executes `docker run --rm -dit` (not via host script)
- [x] Container starts in detached mode
- [x] Container has stable name: `agents-runner-tui-it-<task_id>`
- [x] App records container name/ID in Task payload
- [x] Terminal script no longer runs `docker run`

## Notes
- Use `--rm` to keep auto-remove behavior
- Use `-d` for detached, `-i` for interactive stdin, `-t` for TTY
- This enables task 004 (terminal attach) to work properly

## Completion Notes

**Date:** 2025-01-20  
**Commit:** a665482

**Implementation:**
1. Added `subprocess` import to enable app-side Docker command execution
2. Modified `_build_docker_command()` to support detached mode:
   - Added `detached: bool = False` parameter
   - Use `-dit` flags when detached=True, `-it` when False
   - Added `--rm` flag for auto-remove behavior
3. Updated `launch_docker_terminal_task()` to launch container app-side:
   - Pull Docker image with `subprocess.run()` before launch
   - Run `docker run --rm -dit` with `subprocess.run()` (app-side)
   - Store container name in `task.container_id` field
   - Added comprehensive error handling for pull and launch failures
4. Modified `_build_host_shell_script()` to attach mode:
   - Added `attach_mode: bool = False` parameter
   - When attach_mode=True, script runs `docker attach` instead of `docker run`
   - Removed `docker rm -f` from cleanup (--rm handles auto-removal)
   - Removed docker_pull_cmd and docker_cmd parameters (now app-side)

**Key Changes:**
- Container lifecycle now owned by app process, not terminal script
- Terminal script only attaches to existing container
- Container starts detached with stable name before terminal opens
- Proper separation of concerns: app manages container, terminal provides UI

**Testing:**
- Python syntax validated with py_compile
- No syntax errors detected

**Status:** ✅ Complete - All acceptance criteria met
