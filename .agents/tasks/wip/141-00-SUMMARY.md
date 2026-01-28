# Issue #141 Task Breakdown Summary

**Issue:** Qt Timer Cross-Thread Warnings and Staging Cleanup ENOTEMPTY  
**GitHub:** Midori-AI-OSS/Agents-Runner#141  
**Created:** 2025-01-27

## Problem Statement

Two related issues occur when running the agents-runner:

1. **Qt Timer Warnings** - Cross-thread timer manipulation in ArtifactFileWatcher
   ```
   QObject::killTimer: Timers cannot be stopped from another thread
   QObject::startTimer: Timers cannot be started from another thread
   ```

2. **Staging Cleanup Failure** - Directory not empty error during cleanup
   ```
   Staging cleanup failed: [Errno 39] Directory not empty: '...artifacts/.../staging'
   ```

## Task Files Created

### Investigation Phase (Do First)
1. **141-01-reproduce-timer-warnings.md** → `artifact_file_watcher.py`
   - Reproduce Qt timer warnings with debug logging
   - Identify thread IDs and call stacks

2. **141-02-reproduce-staging-cleanup.md** → `artifacts.py`
   - Reproduce ENOTEMPTY error with detailed logging
   - Identify what remains in staging directory

3. **141-05-verify-watcher-lifecycle.md** → `artifacts_tab.py`
   - Audit all ArtifactFileWatcher instantiations
   - Document lifecycle management (create/start/stop/destroy)

### Fix Phase (After Investigation)
4. **141-03-fix-timer-thread-affinity.md** → `artifact_file_watcher.py`
   - Fix Qt timer thread affinity issues
   - Depends on: 141-01
   - Use moveToThread() or Qt.QueuedConnection

5. **141-04-fix-staging-cleanup-logic.md** → `artifacts.py`
   - Fix staging cleanup to handle nested directories
   - Depends on: 141-02
   - Replace manual loop with shutil.rmtree() + retry

### Testing Phase (Verify Fixes)
6. **141-06-test-timer-fix.md** → `artifact_file_watcher.py` (verification)
   - Test timer fix in multiple scenarios
   - Depends on: 141-03
   - Confirm no warnings appear

7. **141-07-test-cleanup-fix.md** → `artifacts.py` (verification)
   - Test cleanup fix in multiple scenarios
   - Depends on: 141-04
   - Confirm no ENOTEMPTY errors

## Execution Order

**Parallel Track 1 (Timer Issue):**
```
141-01 (reproduce) → 141-03 (fix) → 141-06 (test)
```

**Parallel Track 2 (Cleanup Issue):**
```
141-02 (reproduce) → 141-04 (fix) → 141-07 (test)
```

**Supporting Investigation:**
```
141-05 (lifecycle audit) - can run anytime
```

## Key Files Involved

- `agents_runner/docker/artifact_file_watcher.py` - Qt file watcher with QTimer
- `agents_runner/artifacts.py` - Artifact collection and staging cleanup
- `agents_runner/ui/pages/artifacts_tab.py` - UI that may instantiate watchers

## Notes

- Each task targets exactly **one file**
- Investigation tasks add temporary debug logging (removed after fixes)
- Fixes must not break existing artifact collection functionality
- Both issues may be related (watcher lifecycle vs. staging cleanup race)
