# TASK-LAUNCH-001: Wait for container readiness before opening terminal

## Problem
Terminal opens immediately after container launch without waiting for pre-container setup to complete. This causes:
- User sees incomplete/partial preflight output
- Terminal attaches before clone completes
- Race conditions between setup and user interaction

## Root Cause
In `agents_runner/ui/main_window_tasks_interactive_docker.py`:
- Container launched detached (line 270-275)
- Container state checked only for "Running" (line 285-303)
- Terminal launched immediately via `launch_in_terminal()` (line 362)
- No wait for preflight completion marker

## Acceptance Criteria
1. Terminal opens only after all container preflight scripts complete
2. Git clone completes before terminal becomes interactive
3. User sees complete preflight output, not partial
4. No race conditions between setup and terminal attach
5. Appropriate error handling if preflights fail

## Implementation Notes
- The completion marker infrastructure already exists (see `_build_completion_marker_script()` line 195)
- Use similar pattern but for "preflight ready" marker
- Poll for marker file existence before calling `launch_in_terminal()`
- Consider timeout (e.g., 5 minutes) for preflight completion
- Show progress indicator while waiting (optional but nice-to-have)

## Files to Modify
- `agents_runner/ui/main_window_tasks_interactive_docker.py` (add preflight completion check before line 362)

## Verification Steps
1. Create task with slow preflight (add `sleep 10` to test)
2. Verify terminal doesn't open until after sleep completes
3. Verify all preflight logs visible when terminal opens
4. Test with failing preflight, verify error handling
5. Verify reattach still works without re-running preflights
