# Task 002: Add `cleanup_by_size()` oldest-first size-driven cleanup in cleanup.py

**File:** `agents_runner/environments/cleanup.py`

**Dependencies:** Task 001 (`get_workspace_tree_size`)

## Objective
Add a size-driven cleanup function that removes the oldest finished task workspaces first until total workspace size falls under a configured threshold.

## Requirements
1. Create function `cleanup_by_size(*, threshold_gb: int, task_payloads: Iterable[dict[str, Any]], active_task_ids: set[str], finalizing_task_ids: set[str], data_dir: str | None, on_log: Callable[[str], None] | None = None) -> int` that returns the count of workspaces removed. Signature follows the pattern of `cleanup_retained_task_workspaces`.
2. Identify candidate workspaces: filter payloads where:
   a. `workspace_type == "cloned"` (match retention cleanup pattern)
   b. `status` is in `_FINISHED_STATUSES` (`{"done", "failed", "error", "cancelled", "killed"}`)
   c. Task ID is NOT in `active_task_ids` or `finalizing_task_ids`
   d. Deduplicate by `(env_id, task_id)` key (follow pattern from `cleanup_retained_task_workspaces`)
3. Sort candidates by `finished_at` timestamp, oldest first. Reuse the existing `_payload_finished_at_s()` helper (line 40 of cleanup.py) for timestamp extraction — do not re-implement timestamp parsing. If `_payload_finished_at_s` returns `None`, fall back to the workspace directory's `st_mtime` using `os.path.getmtime()`.
4. Use the new `get_workspace_tree_size(Path(data_dir))` (Task 001) to measure the current total size of the workspace root directory.
5. Iterate candidates in oldest-first order, calling the existing `cleanup_task_workspace(env_id=..., task_id=..., data_dir=data_dir, on_log=on_log)` on each, until the total size (re-measured after each removal with `get_workspace_tree_size`) falls below `threshold_gb * (1024**3)` bytes. Stop early if threshold is already met before any removals.
6. For obtaining the workspace directory path to check `st_mtime`, use `task_workspace_path(env_id, task_id=task_id, data_dir=data_dir)` imported from `agents_runner.environments.task_workspaces`.
7. Return the number of workspaces removed.
8. If `threshold_gb <= 0`, treat as no-op (return 0).

## Acceptance Criteria
- Finished workspaces are sorted oldest-first by `finished_at` with `st_mtime` fallback.
- Workspaces are removed one at a time, with size re-checked after each removal.
- Only `workspace_type == "cloned"` workspaces with finished statuses are candidates.
- Active and finalizing tasks are never removed.
- Deduplication by `(env_id, task_id)` prevents double-removal.
- Returns correct count of removed workspaces.
- Does not crash if `finished_at` is missing from all payloads (falls back to mtime).
- Non-positive `threshold_gb` is a no-op.

## Notes
- Follow existing code conventions in `cleanup.py`.
- Reuse `cleanup_task_workspace()` and `_payload_finished_at_s()` — do not duplicate their logic.
- Reuse `_FINISHED_STATUSES` already defined in the module.
- Use the existing module-level `midori_ai_logger` for logging.
- Import `task_workspace_path` from `agents_runner.environments.task_workspaces`.
