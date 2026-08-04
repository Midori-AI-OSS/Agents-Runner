# Fix: Past tasks silently fail when clicking "Create PR"

## Issue
GitHub issue #376: "Past tasks can not be pred" (past tasks cannot be PR'd).

When a user opens a past (killed/cancelled) task in the Details view and clicks the
Review -> Create PR button, nothing happens. No dialog, no error, no PR.

## Root Cause

`_on_task_pr_requested` in `agents_runner/ui/main_window_task_review.py:24-28`
looks up the task in `self._tasks`, but archived past tasks are never registered there:

```python
def _on_task_pr_requested(self, task_id: str) -> None:
    task_id = str(task_id or "").strip()
    task = self._tasks.get(task_id)
    if task is None:
        return  # <-- silent no-op
```

Archived past tasks are loaded from `tasks/done/*.toml` files but only stored in
local variables in `_open_task_details` (main_window_task_events.py:46-51) and
`_load_past_tasks_batch` (main_window_dashboard.py:60-73) — never added to `self._tasks`.

This means the PR button renders enabled (the archived TOML preserves `workspace_type`),
but clicking it does nothing because the handler can't find the task.

## What To Do

Modify `_on_task_pr_requested` in `agents_runner/ui/main_window_task_review.py`:

1. Add imports at the top of the file:
   - `from agents_runner.persistence import deserialize_task`
   - `from agents_runner.persistence import load_task_payload`
   - `from agents_runner.ui.task_model import Task`
2. If `self._tasks.get(task_id)` returns None, attempt to load the task from archive
   using `load_task_payload(self._state_path, task_id, archived=True)` — follow the
   same pattern already used in `_open_task_details` (main_window_task_events.py:48-51).
   - Note: `self._state_path` is available via the `MainWindowHints` mixin contract
     (`_mixin_hints.py` line 67).
3. Deserialize it with `deserialize_task(Task, payload)`.
4. Register the loaded task in `self._tasks`:
   ```python
   self._tasks[task_id] = task
   ```
   (No proxy wiring is needed for past tasks — they have no active event proxy.)
5. Continue the existing PR flow with the now-resolved task object.

## Verification

- Kill/cancel a cloned-workspace task
- Restart the app
- Open the task from the Past Tasks tab
- Click Review -> Create PR
- The PR dialog should appear and the PR should be created

## Review Notes (2026-08-04)

**Status: PASS WITH UPDATES** — Correct diagnosis, actionable scope.

**Updates applied:**
1. Added missing imports that `main_window_task_review.py` needs: `load_task_payload`,
   `deserialize_task`, and `Task` (for `deserialize_task(Task, payload)`).
2. Corrected Step 3: the task previously said "register proxy/event wiring as
   `_open_task_details` does", but `_open_task_details` does NOT register event proxy
   wiring (it only normalizes logs). Removed the misleading reference. A basic
   `self._tasks[task_id] = task` is sufficient since past tasks have no active proxy.
3. Added a note that `self._state_path` is available via `MainWindowHints` (line 67
   of `_mixin_hints.py`), so no special access setup is needed.

**Dependency note:** This task can work standalone (load-from-archive fallback in the
handler), but is more efficient if `376-register-archived-task.md` is completed first
(since `_open_task_details` would then register the task, making the
`self._tasks.get()` lookup succeed without the fallback).
