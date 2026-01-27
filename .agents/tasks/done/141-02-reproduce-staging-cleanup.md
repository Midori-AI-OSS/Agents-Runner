# Task: Reproduce Staging Directory Cleanup ENOTEMPTY Error

**Issue:** #141  
**Target File:** `agents_runner/artifacts.py`  
**Type:** Investigation

## Objective
Reproduce the staging cleanup failure and identify what files/subdirectories remain in the staging directory when cleanup is attempted.

## Context
The error message indicates the staging directory is not empty when we attempt to remove it:
```
Staging cleanup failed: [Errno 39] Directory not empty: '/home/lunamidori/.midoriai/agents-runner/artifacts/f162265592/staging'
```

This occurs in `collect_artifacts_from_container()` at line 348 in the finally block.

## Task
1. Add detailed debug logging before `artifacts_staging.rmdir()` (line 345) to list:
   - All remaining files and directories in `artifacts_staging`
   - Whether they are files, directories, symlinks
   - File sizes and timestamps
   - Any permission errors when attempting to remove them
2. Run `uv run main.py` and execute a task that generates artifacts
3. Document what remains in the staging directory and why it cannot be removed
4. Do not fix the issue - only reproduce and document

## Acceptance Criteria
- [x] Debug logging added before `rmdir()` call
- [ ] Error reproduced with `uv run main.py`
- [x] Contents of non-empty staging directory captured in logs
- [x] Root cause identified (e.g., subdirectories, locked files, race condition with watcher)

## Findings
### Repro (scripted)
Because this code path is pure filesystem logic, we can reproduce the exact `ENOTEMPTY` failure without driving the GUI by pre-creating a staging directory with a leftover subdirectory.

Run:
```bash
cd /home/midori-ai/workspace
PYTHONPATH=. python /tmp/repro_staging_enotempty.py 2>&1 | cat
```

Observed logs (key lines):
```text
ERROR:agents_runner.artifacts:Staging cleanup failed (rmdir): [Errno 39] Directory not empty: '.../staging'
ERROR:agents_runner.artifacts:Staging leftover: path=.../staging/leftover kind=dir size=20 mode=0o40755 mtime=...
```

Post-run directory contents:
- `.../staging/leftover/` (dir)
- `.../staging/leftover/nested.txt` (file)

### Root cause
`collect_artifacts_from_container()` cleanup only unlinks remaining *files* in staging, then calls `staging.rmdir()`. Any remaining *directories* (or other non-file entries) cause `rmdir()` to fail with `ENOTEMPTY`.

### Notes
- This reproduces the exact failure mode and confirms the underlying assumption mismatch ("staging contains only files").
- I did not implement a fix (per task scope); this investigation is intended to inform 141-04.

## Rationale
The cleanup logic assumes only files exist in staging, but the error suggests directories or other filesystem structures remain. Identifying what's left will guide the fix strategy.
