# Fix: PR URL cannot be persisted to archived past tasks

## Issue
GitHub issue #376: "Past tasks can not be pred" — secondary dead path.

When a background worker successfully creates a PR for a task and emits the PR URL
via `_on_host_pr_url` (main_window_task_events.py:578-589), the handler also does a
`self._tasks.get(task_id)` lookup and silently returns if the task is not found.
For archived past tasks (not in `self._tasks`), the PR URL is never persisted,
so the "Open PR" button never appears for that task on subsequent app restarts.

## Root Cause

`_on_host_pr_url` in `agents_runner/ui/main_window_task_events.py:578-581`:

```python
def _on_host_pr_url(self, task_id: str, pr_url: str) -> None:
    task = self._tasks.get(task_id)
    if task is None:
        return
    task.gh_pr_url = str(pr_url or "").strip()
    # ... persists to state and updates dashboard
```

## What To Do

Modify `_on_host_pr_url` in `agents_runner/ui/main_window_task_events.py`:

1. If `self._tasks.get(task_id)` returns None, attempt to load the task from archive
   using `load_task_payload(self._state_path, task_id, archived=True)`.
2. Deserialize it with `deserialize_task(Task, payload)`.
3. Register the loaded task in `self._tasks`.
4. Set `task.gh_pr_url` and continue the existing persistence flow.

## Verification

- After fixing the primary PR flow (task 376-primary-pr-past-task), verify that
  successfully creating a PR for a past task persists the PR URL so that on the
  next app restart, the Review button shows "Open PR" and opens the existing PR.

## Review Notes (2026-08-04)

**Status: PASS (no updates needed)** — Correct diagnosis, well-scoped, all details present.

**Verified:**
- `load_task_payload`, `deserialize_task`, and `Task` are already imported in
  `main_window_task_events.py` (lines 26, 27, 35), so no import changes needed.
- `self._state_path` is available via `MainWindowHints` mixin (`_mixin_hints.py` line 67).
- After registering in `self._tasks`, the existing `self._schedule_save()` call (line
  589) correctly handles archiving: `_save_state` (main_window_persistence.py:147-152)
  passes `archived=self._should_archive_task(task)`, which returns True for killed/
  cancelled tasks with `finalization_state == "done"` (line 49). The PR URL will be
  saved to the correct `tasks/done/` path.

**Dependency:** This task depends on `376-primary-pr-past-task.md` (or
`376-register-archived-task.md`) — the task must be findable in `self._tasks` for
the PR URL persistence to work. If neither prerequisite is done, the fallback
logic added to `_on_host_pr_url` handles the load-from-archive case independently.
