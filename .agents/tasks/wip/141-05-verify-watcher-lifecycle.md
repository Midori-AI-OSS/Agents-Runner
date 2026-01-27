# Task: Verify ArtifactFileWatcher Lifecycle Management

**Issue:** #141  
**Target File:** `agents_runner/ui/pages/artifacts_tab.py`  
**Type:** Investigation

## Objective
Identify where ArtifactFileWatcher instances are created, started, stopped, and destroyed, and verify proper lifecycle management.

## Context
If watchers are not properly stopped before the staging directory is cleaned up, it could cause both the timer warnings and the cleanup failures.

## Task
1. Search for all instantiations of `ArtifactFileWatcher` in the codebase
2. Document for each usage:
   - Where it's created (which thread/context)
   - When `start()` is called
   - When `stop()` is called
   - Parent QObject used
   - Whether it's properly cleaned up before staging directory removal
3. Add assertions or logging to verify watchers are stopped before cleanup
4. Document findings in `/tmp/agents-artifacts/watcher-lifecycle.md`

## Acceptance Criteria
- [x] All ArtifactFileWatcher instantiations located and documented
- [x] Lifecycle management verified for each usage
- [x] Any missing `stop()` calls identified
- [x] Recommendations provided for proper lifecycle in relation to staging cleanup

## Completion Notes (2026-01-27)
- Located all instantiations: only in `ArtifactsTab._switch_to_staging_mode`.
- Verified lifecycle stop points:
  - Stops on mode switch to encrypted (`_switch_to_encrypted_mode`).
  - Stops when tab is hidden (`hideEvent`).
  - Stops any existing watcher before creating a new one.
- Added minimal, env-gated lifecycle debug logging:
  - Set `AGENTS_RUNNER_WATCHER_LIFECYCLE_DEBUG=1` to enable.
  - Logs to stderr and `/tmp/agents-artifacts/141-05-watcher-lifecycle.log`.
- Findings documented in `/tmp/agents-artifacts/watcher-lifecycle.md`.

## Rationale
If the file watcher is still running when we try to clean up the staging directory, it could hold filesystem handles or cause race conditions. Proper lifecycle management is critical for both issues.
