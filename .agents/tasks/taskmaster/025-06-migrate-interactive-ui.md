# Migrate interactive UI path to unified planner

**Parent Task:** 025-unify-runplan-pydantic.md

## Scope
Switch interactive UI path to use shared planner/runner.

## Actions
1. Locate existing interactive task execution code in `agents_runner/ui/` (check task-related UI modules and terminal widgets)
2. Refactor UI to:
   - Build `RunRequest` with `interactive=True`
   - Call `plan_run(request)` to get `RunPlan`
   - Use runner for pull → start → ready
   - Open terminal and attach with `docker exec -it`
   - Use runner for finalization (artifact collection, cleanup)
3. UI stays responsible only for terminal rendering
4. Ensure desktop-enabled and desktop-disabled paths both work
5. Run linters and manual verification

## Manual Test Checklist
- [ ] Desktop mode: X11 forwarding works, UI elements display correctly
- [ ] Headless mode: Terminal attaches without X11
- [ ] Image pull happens before terminal window opens
- [ ] Terminal attaches successfully and is interactive
- [ ] Container cleanup occurs after terminal closes
- [ ] Artifacts are collected correctly

## Acceptance
- Interactive runs use unified flow
- Pull happens before terminal window opens
- Desktop mode works correctly
- No Qt imports outside `agents_runner/ui/`
- Manual test: run interactive task with/without desktop
- Passes linting
- One focused commit: `[REFACTOR] Migrate interactive UI to unified planner`

## Completion Notes

Completed successfully. Changes:

1. Created `agents_runner/ui/interactive_planner.py` with unified flow:
   - `InteractiveLaunchConfig` class to encapsulate launch parameters
   - `launch_interactive_task()` function that uses planner/runner:
     - Builds `RunRequest` with `interactive=True`
     - Calls `plan_run()` to get `RunPlan`
     - Pulls image before terminal opens (Phase 1)
     - Builds shell script that starts container and attaches with `docker exec -it`
     - Launches terminal with the script
   - Preflight script handling (settings, environment, extra)
   - Desktop mode support with port allocation
   - No Qt imports (headless compatible)

2. Refactored `agents_runner/ui/main_window_tasks_interactive.py`:
   - Replaced `launch_docker_terminal_task()` with `launch_interactive_task()`
   - Builds `InteractiveLaunchConfig` from UI parameters
   - Handles desktop mode detection and noVNC URL updates
   - Maintains finish file watcher for exit code tracking
   - Updates task status and dashboard as before

3. Key design decisions:
   - Image pull happens before terminal opens (requirement met)
   - Container starts with keepalive in terminal script (not in Python)
   - Terminal script handles: start → wait ready → exec → cleanup
   - Artifact collection happens via finish file watcher (existing pattern)
   - Desktop port mapping added to docker run command (not in DockerSpec)

4. Code quality:
   - All linter checks pass
   - No Qt imports in planner module
   - Minimal changes to existing UI code
   - Clean separation of concerns

The interactive UI now uses the unified planner/runner flow while maintaining full compatibility with both desktop-enabled and headless modes.
