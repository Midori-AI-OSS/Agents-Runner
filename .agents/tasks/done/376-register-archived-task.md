# Fix: Register archived task in self._tasks when opened via _open_task_details

## Issue
GitHub issue #376: "Past tasks can not be pred" — contributing factor.

When `_open_task_details` (main_window_task_events.py:46-51) opens an archived past
task, it deserializes the task from `tasks/done/*.toml` into a **local variable** but
never registers it in `self._tasks`. This means any subsequent operation on that task
(closing, PR creation, status updates, etc.) will fail to find it.

## Root Cause

`_open_task_details` in `agents_runner/ui/main_window_task_events.py:46-51`:

```python
task = self._tasks.get(task_id)
if task is None:
    payload = load_task_payload(self._state_path, task_id, archived=True)
    if not isinstance(payload, dict):
        return
    task = deserialize_task(Task, payload)
    # ... process logs ...
# task is never stored in self._tasks
```

## What To Do

Modify `_open_task_details` in `agents_runner/ui/main_window_task_events.py`:

1. After successfully deserializing the archived task (after the log normalization
   block, before `self._details.show_task(task)`), register it in `self._tasks`:
   ```python
   self._tasks[task_id] = task
   ```
2. No event proxy wiring is needed: past tasks have no active `TaskEventProxy`.
   (Active tasks get proxy wiring during task startup, not during detail-page
   loading, so there is no existing pattern to replicate here.)

**Note:** `_save_state` (main_window_persistence.py:147-152) already handles
archiving correctly for registered tasks via `self._should_archive_task(task)`,
which returns True for killed/cancelled tasks with `finalization_state == "done"`
(line 49). No additional save-path changes are needed.

**Out of scope:** `_load_past_tasks_batch` in `main_window_dashboard.py:60-73`
has the same pattern (loads into local variable, never registers). That path is
for dashboard row rendering only and does not need `self._tasks` registration.
If a future task needs it, handle separately.

## Verification

- Kill/cancel a task and restart the app
- Open the task from Past Tasks tab
- Verify the task is now in `self._tasks` (it should be findable by downstream handlers)
- The primary PR fix (376-primary-pr-past-task) should be able to find it without
  needing to re-load from archive

## Review Notes (2026-08-04)

**Status: PASS WITH UPDATES** — Correct diagnosis at the right level (contributing factor).

**Updates applied:**
1. Replaced vague "register any event proxy wiring if applicable" with explicit
   guidance: no proxy wiring is needed for past tasks. Active tasks get proxy wiring
   during task startup, not during detail-page loading, so there is no pattern to
   replicate.
2. Added note confirming that `_save_state` correctly handles archiving for
   registered tasks via `_should_archive_task`.
3. Added scope note: `_load_past_tasks_batch` (dashboard.py:60-73) has the same
   pattern but is intentionally out of scope — it's for dashboard rendering only.

**Dependency:** This is a foundational fix. Completing this task makes the fallback
logic in `376-primary-pr-past-task.md` and `376-pr-url-past-task.md` unnecessary
for the detail-page flow (though those fallbacks remain valuable for robustness).
