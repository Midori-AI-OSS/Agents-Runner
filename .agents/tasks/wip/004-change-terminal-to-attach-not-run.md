# Task 004: Change Terminal Script to Attach (Not Run)

## Objective
Change the terminal window to attach to an already-running container instead of running the container.

## Context
- After task 003, the app launches the container in detached mode
- Terminal window should now just attach to the existing container
- This allows detach/reattach without killing the container

## Requirements
1. Terminal script should execute: `docker attach <container_name>`
2. Remove `docker run` command from terminal script
3. Remove `docker rm -f` from terminal script EXIT trap
4. Container continues running if user closes terminal window

## Location to Change
- File: `agents_runner/ui/main_window_tasks_interactive_docker.py`
- Function: `_build_host_shell_script` (or replace with simpler attach script)

## Acceptance Criteria
- [ ] Terminal script runs `docker attach <container_name>` only
- [ ] Terminal script does NOT run `docker run`
- [ ] Terminal script does NOT remove container on exit
- [ ] Closing terminal window leaves container running
- [ ] User can reattach by running the same command again

## Notes
- Users can detach without killing with: Ctrl-p, Ctrl-q
- Consider adding a UI "Reattach" button that reopens terminal with attach command
- Depends on task 003 (container must be running before attach)
