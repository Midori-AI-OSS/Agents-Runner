# Bug: GH-managed "Run Agent" cloning UX/regression

## Summary
On the **New Task** page, clicking **Run Agent** in a GitHub-managed environment can appear to do nothing while the repo is being cloned/branched. The task exists and cloning logs may be emitted, but the UI stays on the New Task page, so the user cannot see the task or its logs until later.

If the user manually navigates to the task viewer during cloning and is watching the clone step, completing the clone can forcibly navigate them back to the dashboard (“kicking them out” of the current view).

In some cases, tasks can remain stuck in `cloning` indefinitely (never transitioning to `queued`/`pulling`), with no visible clone logs.

## Expected
- As soon as the user clicks **Run Agent**, the app should navigate to a view where progress is visible (dashboard and/or task details), and the task should visibly enter `cloning` immediately.
- Completing the clone/branch prep should not forcibly navigate away from whatever view the user is currently using.
- `cloning` should always resolve to either success (`queued`/`pulling`) or failure (with an error) within a bounded time.

## Observed
- Example stuck task: `~/.midoriai/codex-container-gui/tasks/9acbeaa656.json` with `status="cloning"` and `logs=[]` (no `"[gh] cloning …"` line).

## Likely cause
- GH cloning/branch-prep runs in a `QThread` via `GhManagementBridge`, but the UI updates are wired through nested Python functions connected as signal handlers. Depending on PySide6 behavior, those callables can be invoked on the wrong thread (causing Qt thread-affinity errors) or not delivered reliably, leaving the task stuck in `cloning`.

## Required fix (enforced)
- GitHub repo preparation (clone + branch prep) must run through the existing **preflight task runner** so logs are streamed into the task viewer via the same path as other preflight output (not a separate `QThread` + custom signals).
- The user must be able to watch clone progress live in the task viewer; no “silent cloning” in the background.
- Completion of the clone step must not force-navigation away from the user’s current view.

## Notes / Ideas
- Root cause for “no immediate feedback”: GH prep path returns early before calling `_show_dashboard()`, so dashboard/info updates remain hidden until GH prep completes.
- The GH prep subprocesses use `capture_output=True`, so a blocked git operation produces no streaming output; log explicit “starting clone/branch prep” lines and consider basic lock detection for `.git/index.lock`.
- GH prep should be a visible “preflight” stage (before Docker pull/run) so it behaves like other preflight work.
- Prefer connecting `GhManagementBridge` signals to real `QObject` slots on `MainWindow` (not lambdas/nested functions), and include `task_id` in the signal payloads so the slots can safely update the correct task from the UI thread.
