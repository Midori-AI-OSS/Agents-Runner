# Task — Interactive tasks lifecycle redesign

## Problem

Interactive tasks are not fully lifecycle-managed by the app (the “run” is owned by a host terminal script). This makes restart recovery and post-run cleanup/finalization unreliable and contributes to tasks getting stuck, losing exit information, and losing post-run automation (artifact collection / PR / cleanup).

User direction: Interactive should behave like a normal task (same lifecycle + finalization), but the user interacts with the agent in the container via a terminal window that the app opens.

## Scope (design + notes)

- Capture requirements and propose an app-owned lifecycle for interactive tasks (detach/reattach, cleanup, terminal outcome recording).
- This document is meant to help other agents implement the redesign.

## Requirements (what we want)

- App owns lifecycle (start/stop/kill/status/exit code) and post-run finalization (cleanup, PR policy, artifacts).
- User interacts via a host terminal window attached to the running container.
- Detach/reattach must work across UI restarts.
- Keep `auto_remove` behavior on container shutdown (container should be removed once it exits).

## What the code does today (why it’s janky)

Key points from current implementation:

- Interactive is launched via a generated host shell script that runs `docker run -it --name <name> ...` in the user’s terminal.
  - Code: `agents_runner/ui/main_window_tasks_interactive_docker.py`
- That host script writes a plaintext finish file to `~/.midoriai/agents-runner/interactive-finish-<task_id>.txt`, then removes the container with `docker rm -f` in an `EXIT` trap.
  - Code: `agents_runner/ui/main_window_tasks_interactive_docker.py:_build_host_shell_script`
- The UI only discovers completion by polling for that finish file in-process, during the same app session that launched it.
  - Code: `agents_runner/ui/main_window_tasks_interactive.py:_start_interactive_finish_watch`
  - On success it calls `agents_runner/ui/main_window_tasks_interactive_finalize.py:_on_interactive_finished`

Why this fails in practice:

- If the UI restarts, there is no watcher thread, so a completed interactive task can sit in “running/unknown” indefinitely.
- On restart, task recovery uses `docker inspect` (`_try_sync_container_state`) but the interactive container is often already removed by the host script, so “inspect” fails and the task becomes generic “failed (exit_code=1)”.
  - Code: `agents_runner/ui/main_window_persistence.py:_try_sync_container_state`
- Finalization currently tries to collect artifacts “from the container”, but the container might not exist anymore, so finalization can error and never reach `finalization_state="done"`.
  - Code: `agents_runner/ui/main_window_task_recovery.py:_finalize_task_worker`

## Naming (current conventions)

As of the latest naming cleanup:

- Normal task containers: `agents-runner-<random>` (example: `agents-runner-a1b2c3d4e5`)
- Preflight containers: `agents-runner-preflight-<random>`
- Interactive task containers: `agents-runner-tui-it-<task_id>`

Note: `Task.container_id` often stores a container *name* (not an ID). Recovery paths currently pass it to Docker commands as an identifier (Docker accepts names).

## Implications of keeping auto-remove

If the container is removed on exit, restart recovery cannot depend on `docker inspect` finding an `exited` container later. The design needs a host-visible completion signal that survives container removal.

## Proposed design: app-owned container + terminal attach UX

The simplest “acts like a normal task, but interactive in a terminal” model is:

1) App starts the container (detached) and records its identity in the persisted task payload.
2) App opens a terminal window that attaches to the already-running container for user interaction.
3) App monitors container state and logs (and can be restarted to resume monitoring).
4) On exit, container is auto-removed, but a host-visible completion marker remains so restart recovery can finalize.

This removes the split ownership (terminal script no longer does `docker run` or `docker rm`).

### Container launch shape

Use the normal-task shape as a template (it already mounts artifact staging and tails logs):

- Normal task runner mounts a host staging dir to `/tmp/agents-artifacts` in-container.
  - Code: `agents_runner/docker/agent_worker.py` includes `-v <artifacts_staging_dir>:/tmp/agents-artifacts`
- Normal tasks already tail logs via `docker logs -f`.
  - Code: `agents_runner/docker/agent_worker.py` and restart recovery tail `agents_runner/ui/main_window_task_recovery.py:_ensure_recovery_log_tail`

Interactive variant should:

- Start the container with a stable name (already done): `agents-runner-tui-it-<task_id>`
- Start detached but with a TTY so `docker attach` works well: `docker run --rm -dit --name <name> ...`
- Mount the task’s host staging directory to `/tmp/agents-artifacts` (same as normal tasks)
- Run the agent as the main process so the container exits when the agent exits (so auto-remove triggers cleanly)

### Terminal attach/detach

Terminal command should be “attach to existing container” (not “run the container”):

- `docker attach <container_name>`

Expected behavior:

- Closing the terminal window should not destroy the container; the container continues to run and the UI still controls stop/kill.
- Reattach is just opening another terminal and running the same attach command.

(If we want detach without killing the agent, document `Ctrl-p` then `Ctrl-q`, and/or provide a UI “Reattach” button that just opens a new terminal.)

## Completion marker (survives auto-remove)

Write a completion marker into the mounted `/tmp/agents-artifacts` dir before the container exits:

- Path (host-visible): `~/.midoriai/agents-runner/artifacts/<task_id>/staging/interactive-exit.json`
  - This is the host path behind the container’s `/tmp/agents-artifacts/interactive-exit.json`

Contents (keep minimal; avoid secrets):

```json
{
  "task_id": "abcd1234ef",
  "container_name": "agents-runner-tui-it-abcd1234ef",
  "exit_code": 0,
  "started_at": "2026-01-18T10:00:00Z",
  "finished_at": "2026-01-18T10:05:00Z",
  "reason": "process_exit"
}
```

How to ensure it’s written:

- Wrap the agent launch in a shell `trap` inside the container script so `EXIT` writes the JSON.
- Note: `SIGKILL` can bypass traps; if the UI is alive, it can also record `docker wait` exit code as a backup.

## Artifact strategy (no container dependency after exit)

Because the container is auto-removed on exit, finalization must not require `docker cp` from the container after-the-fact.

Make the staging directory mount the source of truth:

- Mount host staging dir to `/tmp/agents-artifacts` in the interactive container.
- Anything we care about after exit (logs, completion marker, screenshots, PR metadata) should be written into `/tmp/agents-artifacts`.
- Finalization can then encrypt/collect from the host staging dir even when the container is gone.

This matches the “artifact info” model already in code:

- `agents_runner/artifacts.py:get_artifact_info()` defines the container artifacts dir as `/tmp/agents-artifacts/`.

## Relevant existing machinery (reuse it)

There is already a restart recovery loop and a background finalizer for normal tasks:

- Startup reconciliation calls `_reconcile_tasks_after_restart()`:
  - `agents_runner/ui/main_window_persistence.py:_load_state`
  - Implementation: `agents_runner/ui/main_window_task_recovery.py:_reconcile_tasks_after_restart`
- When a task is active, recovery can tail logs via `docker logs -f`:
  - `agents_runner/ui/main_window_task_recovery.py:_ensure_recovery_log_tail`
- Finalization is tracked via `Task.finalization_state` and runs in a worker thread:
  - `agents_runner/ui/main_window_task_recovery.py:_queue_task_finalization`
  - `agents_runner/ui/main_window_task_recovery.py:_finalize_task_worker`

The interactive redesign should plug into those same mechanisms, but must avoid any “needs the container after exit” assumptions because interactive containers are expected to be auto-removed.

## Restart recovery behavior (interactive-specific)

On startup, for each interactive task that is not finalized:

1) If the completion marker exists in staging:
   - Set status `done/failed` based on `exit_code`
   - Set `finished_at`
   - Queue finalization (host-staging based)
2) Else if the container exists and is running:
   - Set status `running`
   - Start log tail (`docker logs -f`) so UI has logs
   - Show UI affordance to “Attach” (open terminal)
3) Else (no marker, no container):
   - Mark `status="unknown"` or “failed (unrecoverable)” with a clear error
   - Still run best-effort finalization/cleanup that does not require the container (user preference: try finalization even when missing container)

## Implementation mapping (where to change)

Likely touch points for an implementation agent:

- Replace “terminal owns `docker run`” with “app starts container + terminal attaches”:
  - `agents_runner/ui/main_window_tasks_interactive_docker.py`
- Store and use the same staging dir mount as normal tasks:
  - Mirror normal runner behavior from `agents_runner/docker/agent_worker.py`
- Teach recovery to look for the interactive completion marker:
  - `agents_runner/ui/main_window_task_recovery.py` and/or `agents_runner/ui/main_window_persistence.py`
- Avoid container-dependent artifact collection when container is auto-removed:
  - `agents_runner/ui/main_window_task_recovery.py:_finalize_task_worker` (collect from host staging if container missing)

## Acceptance checks (what “fixed” looks like)

- Interactive tasks show logs in the UI while running (tailing `docker logs -f`).
- If the UI is closed mid-run, reopening the app shows the task as running and allows reattach to the same container.
- If the container exits while the UI is closed, reopening the app finalizes the task using the completion marker + host staging (no stuck “unknown” and no missed cleanup/PR prompts).
- Containers do not remain on disk after interactive exit (auto-remove still effective).

## Notes

- This is intentionally separate from “normal task state recovery + finalization across restarts”, but it should reuse the same recovery/finalization primitives where possible.
