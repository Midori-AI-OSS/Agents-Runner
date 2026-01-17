# Task — Interactive tasks lifecycle redesign (INTERACTIVE)

**Task Type:** INTERACTIVE

## Problem

Interactive tasks are not fully lifecycle-managed by the app (external terminal script owns the run). This makes restart recovery and post-run cleanup/finalization unreliable and contributes to tasks getting stuck or losing state.

User direction: Interactive should behave like a normal task (same lifecycle + finalization), but the user interacts with the agent in the container via a terminal window that the app opens.

## Scope

- Capture requirements and propose an app-owned lifecycle for interactive tasks (detach/reattach, cleanup, terminal outcome recording)
- Design a solution that works with the existing `auto_remove` container behavior

## Requirements

- App owns lifecycle (start/stop/kill/status/exit code) and post-run finalization (cleanup, PR policy, artifacts)
- User interacts via a host terminal window attached to the running container
- Detach/reattach must work across UI restarts
- Keep `auto_remove` behavior on container shutdown (container should be removed once it exits)

## Design Constraint: `auto_remove` Behavior

If the container is removed on exit, restart recovery cannot depend on `docker inspect` finding an `exited` container later. The design needs a host-visible completion signal that survives container removal.

Suggested approach:
- Mount a host directory (already exists for artifacts: `/tmp/agents-artifacts`) and have the container write a small completion marker file before exit:
  - `interactive-exit-<task_id>.json` containing `exit_code`, timestamps, and (optionally) a reason
- Run finalization based on that marker + host workspace state, not by inspecting the container after exit

## Related Notes

- This is intentionally separate from "normal task state recovery + finalization across restarts"
- Related brainstorm chunks live under:
  - `.agents/temp/task-system/interactive.md` (if exists)
  - `.agents/temp/task-system/out-of-process-supervisor.md` (if exists)

## Acceptance Criteria

- Design document or implementation plan that addresses:
  - Container lifecycle management (start/attach/detach/reattach/finalize)
  - Completion marker approach for `auto_remove` containers
  - Integration with existing task finalization flow
  - UI/terminal window management
