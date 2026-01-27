# Task: Fix Staging Directory Cleanup to Handle Non-Empty State

**Issue:** #141  
**Target File:** `agents_runner/artifacts.py`  
**Type:** Bug Fix  
**Depends On:** Task 141-02

## Objective
Make staging directory cleanup robust enough to handle subdirectories, nested files, and race conditions with the file watcher.

## Context
The current cleanup logic (lines 334-348 in `collect_artifacts_from_container()`) assumes staging contains only files, but `rmdir()` fails if directories or nested structures exist.

## Task
Replace the file-only cleanup loop with a recursive removal strategy:
1. Replace the manual file removal loop (lines 337-342) with `shutil.rmtree()` or a proper recursive deletion
2. Add retry logic with short delays to handle race conditions with the file watcher
3. Ensure cleanup happens even if encryption fails
4. Log warnings for cleanup failures but don't raise exceptions (best-effort cleanup)
5. Consider stopping the file watcher before cleanup if it exists

## Acceptance Criteria
- [x] Staging cleanup succeeds even with nested directories
- [ ] No `Directory not empty` errors when running `uv run main.py`
- [x] Cleanup is best-effort and logs failures without crashing
- [x] Existing artifact collection functionality preserved

## Completion Notes
- Implemented robust best-effort staging cleanup using `shutil.rmtree()` with retry/backoff.
- Cleanup runs in `finally:` so it executes even if encryption fails.
- Added warning logging on failures (no exceptions raised).
- Commit: 330926a

## Rationale
The staging directory may contain arbitrary filesystem structures. Using `shutil.rmtree()` handles nested directories correctly, and retry logic accounts for filesystem race conditions.
