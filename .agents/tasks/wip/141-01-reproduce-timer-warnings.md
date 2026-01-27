---
status: done
---

# Task: Reproduce Qt Timer Cross-Thread Warnings

**Issue:** #141  
**Target File:** `agents_runner/docker/artifact_file_watcher.py`  
**Type:** Investigation

## Objective
Reproduce and document the Qt timer cross-thread warnings that occur when the ArtifactFileWatcher is created or destroyed from a non-main thread.

## Context
The error messages indicate timers are being started/stopped from threads other than the one that created the QTimer objects:
```
QObject::killTimer: Timers cannot be stopped from another thread
QObject::startTimer: Timers cannot be started from another thread
```

## Task
1. Add temporary debug logging to `ArtifactFileWatcher.__init__`, `start()`, and `stop()` methods to capture:
   - Current thread ID (`threading.current_thread().ident`)
   - Qt thread affinity (`self.thread().objectName()` or pointer)
   - Stack trace of the call
2. Run `uv run main.py` and trigger a task execution to reproduce the warnings
3. Document findings in a comment at the top of the file or in `/tmp/agents-artifacts/`
4. Do not fix the issue - only reproduce and document

## Results
### Debug logging added
Implemented temporary instrumentation in `agents_runner/docker/artifact_file_watcher.py` and committed in small steps.

Notes:
- The debug helper writes to stderr **only** when `AGENTS_RUNNER_TIMER_THREAD_DEBUG=1` is set (to avoid noisy output).

### Warnings reproduced
Ran the GUI with an isolated state dir:
- `AGENTS_RUNNER_STATE_PATH=/tmp/agents-runner-state uv run main.py`

Observed Qt warnings captured in:
- `/tmp/agents-artifacts/141-01-gui.log`

Example excerpt:
```
QObject::killTimer: Timers cannot be stopped from another thread
QObject::startTimer: Timers cannot be started from another thread
```

### Root cause status
**Not confirmed for `ArtifactFileWatcher`.**

Despite:
- starting tasks via GUI automation,
- opening task details,
- creating files in the reported staging directory,

…the added `ArtifactFileWatcher` debug output did not trigger, suggesting the warnings may originate from a different `QTimer` usage (or from Qt internals) rather than this watcher.

### Findings documentation
Written to:
- `/tmp/agents-artifacts/141-01-findings.md`

## Acceptance Criteria
- [x] Debug logging added to track thread creation/usage
- [x] Warnings reproduced with `uv run main.py`
- [ ] Root cause identified (e.g., watcher created in worker thread, stopped in main thread)
- [x] Findings documented with thread IDs and call stacks (where observed)

## Rationale
Understanding exactly when and why Qt complains about cross-thread timer access is essential before attempting a fix.
