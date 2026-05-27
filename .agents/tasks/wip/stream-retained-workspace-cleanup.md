# Stream retained workspace cleanup

## Issue

The retained task workspace cleanup path can still create startup or navigation-adjacent jank because it builds a full in-memory list of archived task payloads before filtering cleanup candidates.

The current cleanup scheduler is driven by the recovery ticker, not by the Settings page directly. The recovery ticker runs every 5 seconds and calls `_maybe_schedule_task_workspace_cleanup()`. Because `_task_workspace_cleanup_last_check_s` is initialized to `0.0`, the first recovery tick after app startup can immediately start the cleanup worker. If the user opens Settings around that moment, the app can feel like Settings triggered the work.

The expensive part is `_run_task_workspace_cleanup()`: it serializes active in-memory tasks, then calls `load_all_done_task_payloads(self._state_path)`, which scans `~/.midoriai/agents-runner/tasks/done`, sorts every `*.toml` filename, opens every archived task file, parses every TOML payload, and returns one large list. Cleanup then filters that list afterward. The goal is to check old tasks one at a time instead.

## Goal

Make retained workspace cleanup polite and incremental:

- Do not run the first cleanup scan immediately after app startup.
- Do not load all archived done-task TOML payloads into memory for background cleanup.
- Evaluate archived tasks one at a time.
- Preserve existing cleanup decisions and safety behavior.
- Leave explicit user-triggered migration scans unchanged.

## Current behavior to preserve

- Retained cleanup still runs from the recovery ticker, not from Settings.
- Cleanup still uses these settings:
  - `task_workspace_cleanup_retention_days`
  - `task_workspace_cleanup_interval_minutes`
  - `task_workspace_cleanup_scan_delay_seconds`
- Cleanup only removes cloned task workspaces for finished tasks older than the retention cutoff.
- Cleanup skips active tasks and tasks with finalization state `pending` or `running`.
- Cleanup dedupes by `(environment_id, task_id)`.
- Cleanup removes both app-data and Scratch-drive workspace candidates through `task_workspace_candidates()`.
- Cleanup safety checks still reject symlinks and non-task paths.
- `Move all tasks` can still build a complete migration list when the user explicitly clicks it.

## Required implementation

### Startup scheduling

- In `agents_runner/ui/main_window.py`, initialize `_task_workspace_cleanup_last_check_s` to the current time instead of `0.0`.
- Use `time.time()` or an equivalent wall-clock value consistent with `_maybe_schedule_task_workspace_cleanup()`.
- Keep `_task_workspace_cleanup_running = False`.
- Result: the first background cleanup cannot start until the configured interval has elapsed.

### Streaming archived task payloads

- Add a new helper in `agents_runner/persistence.py` for cleanup-specific iteration.
- Name recommendation: `iter_done_task_payloads(state_path: str) -> Iterator[dict[str, Any]]`.
- It must:
  - derive the existing done directory via `tasks_done_dir(state_path)`;
  - return/yield nothing if the directory does not exist;
  - use `os.scandir()` or equivalent one-entry-at-a-time directory iteration;
  - consider only regular `*.toml` files;
  - open and parse one TOML file at a time;
  - skip unreadable or invalid files, matching the forgiving behavior of `load_all_done_task_payloads()`;
  - yield only payloads that are dictionaries.
- Do not remove or change `load_all_done_task_payloads()` because migration still uses it for an explicit full-list action.

### One-at-a-time cleanup processing

- Update `agents_runner/ui/main_window_task_recovery.py` so `_run_task_workspace_cleanup()` no longer calls `payloads.extend(load_all_done_task_payloads(...))`.
- Keep active in-memory task serialization small and local.
- Stream archived payloads into cleanup instead of building a complete archived list first.
- Acceptable approaches:
  - Change `cleanup_retained_task_workspaces()` to accept `Iterable[dict[str, Any]]` and pass it a chained iterable of active payloads plus `iter_done_task_payloads(...)`.
  - Or add a cleanup-specific function that consumes one payload at a time while preserving the current filtering logic.
- Prefer the smallest diff that keeps the filtering logic in `agents_runner/environments/cleanup.py`.
- Keep `scan_delay_seconds` behavior attached to actual cleanup candidates, as it is today.

### Public API and imports

- Export the new persistence iterator only if existing import patterns require it. There is no need to add it to `agents_runner/environments/__init__.py`.
- Keep typing precise for Python 3.13+.
- Do not introduce Qt imports outside `agents_runner/ui/`.
- Do not add a new settings key or persistent config.

### Explicitly unchanged paths

- Do not alter `_migration_records()` in `agents_runner/ui/main_window_settings.py`; it may keep using `load_all_done_task_payloads()` because it runs only after the user clicks `Move all tasks`.
- Do not change Settings UI labels, panes, or Scratch-drive status behavior.
- Do not change task archive layout or TOML schema.
- Do not update `README.md`.
- Do not move task files to `done/` as part of this implementation unless explicitly told to close this task; if a task file is moved later, follow the version bump rule in `AGENTS.md`.

## Edge cases

- Missing `tasks/done` directory returns no archived payloads.
- Invalid TOML files are skipped.
- Archived task files deleted during iteration are skipped.
- Active task IDs still override archived task payloads with the same task ID.
- Duplicate archived payloads for the same `(environment_id, task_id)` should still be deduped by cleanup logic.
- If cleanup is already running, `_maybe_schedule_task_workspace_cleanup()` must still do nothing.
- If no task is old enough, no workspace deletion should occur and no cleanup log needs to be emitted.

## Verification

Run the required checks:

```bash
uv run python -m compileall -q main.py agents_runner
uv run ruff format .
uv run ruff check .
```

Run focused smoke checks without adding persistent tests unless asked:

- Instantiate or monkeypatch enough of the main window cleanup state to confirm `_task_workspace_cleanup_last_check_s` starts near current time.
- Confirm the first `_maybe_schedule_task_workspace_cleanup()` call immediately after startup does not start cleanup when the interval has not elapsed.
- Create a temporary `state.toml` root with several `tasks/done/*.toml` files and confirm the new iterator yields valid payloads one at a time.
- Confirm invalid TOML and non-TOML files are skipped.
- Monkeypatch `cleanup_task_workspace()` and confirm old cloned finished payloads are still selected for cleanup.
- Confirm new, non-cloned, unfinished, active, and finalizing task payloads are skipped.
- Confirm `_migration_records()` still sees archived tasks through `load_all_done_task_payloads()`.

## Commit

Commit the completed implementation with:

```text
[FIX] Stream retained workspace cleanup
```

Before finishing, append the required run-log entry to `/tmp/agents-artifacts/agent-output.md` with actions, results, verification, and any task file movement.
