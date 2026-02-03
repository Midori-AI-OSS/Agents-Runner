# Task system Docker E2E (real Docker socket)

## Goal
Add E2E tests that exercise the task system using a real Docker socket; only mock the agent CLI call (use `echo`).

## Scope
- Task lifecycle + persistence + state transitions
- Real Docker pull/run/stop paths

## Rules
- No heavy mocking (only the agent CLI invocation).
- Use `pytest` via `uv run pytest`.

## Checks
1) Create a task that runs a container and completes; verify state transitions and persisted payloads.
2) Cancel a running task; verify the container is stopped and state is persisted.
3) Kill a running task; verify the container is gone and state is persisted.
