# Bug: Git locked envs show no "task started" feedback

## Summary
When a managed repo/environment is in a Git-locked state (e.g., index.lock or another operation in progress), starting a task can appear to do nothing: the UI does not immediately show a log line indicating that the task start was attempted, and the user has no feedback until the operation eventually fails (or times out).

## Expected
- As soon as the user clicks Run/Start, emit an immediate log line like:
  - `[git] checking repo lock...`
  - `[git] repo appears locked; waiting...`
  - or a clear error message if we choose to fail fast.

## Notes / Ideas
- Detect lock files and/or Git operations in progress early and log explicitly.
- Consider a short "preflight" step that runs before cloning/branch prep and before Docker pull/run, so the task timeline always has an initial user-visible event.

