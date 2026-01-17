# Task — Interactive tasks lifecycle redesign (placeholder)

## Problem

Interactive tasks are not fully lifecycle-managed by the app (external terminal script owns the run). This makes restart recovery and post-run cleanup/finalization unreliable and contributes to tasks getting stuck or losing state.

User direction: Interactive should behave like a normal task (same lifecycle + finalization), but the user interacts with the agent in the container via a terminal window that the app opens.

## Scope (placeholder only)

- Capture requirements and propose an app-owned lifecycle for interactive tasks (detach/reattach, cleanup, terminal outcome recording).
- No implementation in this placeholder task.

## Requirements (what we want)

- App owns lifecycle (start/stop/kill/status/exit code) and post-run finalization (cleanup, PR policy, artifacts).
- User interacts via a host terminal window attached to the running container.
- Detach/reattach must work across UI restarts.
- Keep `auto_remove` behavior on container shutdown (container should be removed once it exits).

## Implications of `auto_remove`

If the container is removed on exit, restart recovery cannot depend on `docker inspect` finding an `exited` container later. The design needs a host-visible completion signal that survives container removal.

Suggested approach:

- Mount a host directory (already exists for artifacts: `/tmp/agents-artifacts`) and have the container write a small completion marker file before exit, e.g.:
  - `interactive-exit-<task_id>.json` containing `exit_code`, timestamps, and (optionally) a reason.
- Run finalization based on that marker + host workspace state, not by inspecting the container after exit.

## Notes

- This is intentionally separate from “normal task state recovery + finalization across restarts”.
- Related brainstorm chunks live under:
  - `.agents/temp/task-system/interactive.md`
  - `.agents/temp/task-system/out-of-process-supervisor.md`
