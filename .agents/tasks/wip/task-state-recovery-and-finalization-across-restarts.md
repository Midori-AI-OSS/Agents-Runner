# Task — Task state recovery + finalization across restarts (data loss)

## Problem

Users report that if the UI closes/crashes while a task is running, the task can later show as `unknown` or get archived without running post-run steps. This causes “data loss” in practice: no cleanup, no PR steps, no artifact collection/finalization, and an unclear final outcome.

This task is specifically about **state being correctly recovered after restart** and ensuring **post-run finalization can run after restart** (idempotently).

## What the code does today (relevant facts)

- Normal tasks persist `container_id` in the task JSON:
  - `agents_runner/persistence.py` `serialize_task()` includes `"container_id": task.container_id`
  - `agents_runner/ui/task_model.py` includes `container_id: str | None`
- On app startup, active tasks are loaded and a best-effort Docker inspect happens:
  - `agents_runner/ui/main_window_persistence.py` `_load_state()` calls `_try_sync_container_state(task)` which runs docker inspect for `task.container_id` and updates `task.status`, `task.exit_code`, timestamps.
- If `_should_archive_task(task)` is true, `_load_state()` archives the task payload immediately.
  - This archive path does not run post-run finalization.

## Goals (MVP)

- On restart, the app reliably determines whether each previously-running task is:
  - still running (container exists and is `running`), or
  - finished (terminal outcome can be inferred), even if the container is missing.
- If a task’s container is still running after restart, the UI can reattach enough to avoid “unknown forever”:
  - resume status updates (poll/inspect), and
  - resume log capture (or provide an explicit “Reattach logs” action).
- When a task is detected as finished on restart, post-run finalization can still happen:
  - artifact collection/finalization
  - workspace cleanup
  - PR policy steps (when applicable)
- Finalization is idempotent and restart-safe (safe to retry if the UI crashes during finalization).

## Why “container exists and is exited/dead” is often not available

- Normal tasks are configured with `auto_remove=True` (`agents_runner/ui/main_window_tasks_agent.py`), so the container is removed after a clean completion path.
- Interactive tasks also remove their container via the host-side script cleanup (tracked separately).

So a restart-recovery design must not depend on `docker inspect` being able to find an exited container.

## Non-goals (for this task)
- Streaming live logs after reattach (nice-to-have; can be a follow-up).

## Design notes (suggested direction)

- Add explicit “finalization state” persisted in the task payload (e.g., `pending/running/done/error`).
- On startup (and optionally periodically), run a reconcile pass:
  - if a task appears finished *or its container is missing* and finalization is pending/error -> run finalization now (best-effort)
  - do not archive tasks until finalization completes (or explicitly record “finalization skipped”)
- Avoid relying on “UI received the done signal” as the only trigger for finalization.

## Acceptance criteria

- Close the UI mid-run, wait for container to finish, reopen UI:
  - Task reaches a terminal outcome (`done/failed/cancelled/killed`) deterministically.
  - Finalization runs (or is visibly queued/running) and completes without manual intervention.
- Close the UI mid-run, reopen UI while the container is still running:
  - Task shows as running (not `unknown`) and continues to receive logs/status updates (or has an explicit reattach control that does so).
- Close the UI mid-run, then reopen UI *after* the container is already missing:
  - Task is treated as finished with “missing container” recorded as a reason/diagnostic.
  - Finalization still runs best-effort (workspace cleanup + PR policy steps where possible; artifact collection skipped/marked if it requires the missing container).
- If the UI crashes during finalization, reopening the UI retries (or offers retry) and does not corrupt task state.

## References

- Reconcile on load: `agents_runner/ui/main_window_persistence.py`
- Task model + status helpers: `agents_runner/ui/task_model.py`
- Persistence: `agents_runner/persistence.py`
- Existing finalization pipeline (UI-coupled today): `agents_runner/ui/main_window_task_events.py`
