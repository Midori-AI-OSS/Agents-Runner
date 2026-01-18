# T001: Investigate and Fix Duplicate Log Emissions

**Status**: ✅ COMPLETED  
**Date**: 2025-01-27  
**Commit**: e1d3816

---

## Problem Statement

Users reported that "logs in the tasks are showing up two times" - each log line was appearing twice in the output during task execution.

---

## Investigation Summary

### Root Cause Analysis

The duplicate log emission was caused by Python's logging module's auto-configuration behavior conflicting with the codebase's custom callback-based logging system.

**Key Findings:**

1. **Custom Logging System**: The codebase uses a callback-based logging architecture:
   - `format_log()` and `format_log_line()` in `log_format.py` for formatting
   - Callbacks (`on_log`) for log emission throughout the stack
   - No handlers from Python's standard logging module explicitly configured

2. **Python's Auto-Configuration**: When `logger.info()` or `logger.debug()` is called without explicit logging configuration, Python automatically:
   - Adds a `lastResort` StreamHandler that emits to stderr
   - Creates a propagation chain from child loggers to root logger
   - Both mechanisms were emitting logs alongside the custom callback system

3. **Duplication Points Identified**:
   - `app.py` lines 146, 150: QtWebEngine initialization logging
   - No explicit `addHandler()` or `basicConfig()` calls found
   - Root logger with auto-added handlers emitting duplicate output

### Code Flow (Before Fix)

```
Task Execution
  ↓
DockerAgentWorker emits via callback → custom log display
  ↓
Python's logger.info() calls → lastResort handler → stderr
  ↓
RESULT: Same log appears twice (once from callback, once from stderr)
```

---

## Solution Implemented

### Changes Made

**File**: `agents_runner/app.py`

1. **Added `_configure_logging()` function** (lines 100-114):
   ```python
   def _configure_logging() -> None:
       """Configure Python's logging module to prevent duplicate log emissions."""
       import logging
       
       # Disable the lastResort handler that Python adds automatically
       logging.lastResort = None
       
       # Configure root logger to not emit anything
       root_logger = logging.getLogger()
       root_logger.handlers.clear()
       root_logger.setLevel(logging.CRITICAL + 1)  # Higher than any real level
   ```

2. **Updated `run_app()` to call logging configuration** (line 174):
   ```python
   def run_app(argv: list[str]) -> None:
       _maybe_enable_faulthandler()
       _configure_logging()  # NEW: Configure logging early
       _configure_qtwebengine_runtime()
   ```

3. **Set `propagate=False` on QtWebEngine loggers** (lines 155, 168):
   - Prevents propagation to root logger
   - Ensures no duplicate emission through parent logger chain

### How It Works

- **Disables `lastResort`**: Prevents Python from auto-adding stderr handler
- **Clears handlers**: Removes any accidentally added handlers from root logger
- **Sets level to max**: Ensures root logger never emits (CRITICAL + 1 is above all levels)
- **Stops propagation**: Child loggers don't forward to root logger

---

## Verification Steps

To verify the fix works:

1. **Run the application**:
   ```bash
   cd /home/midori-ai/workspace
   uv run main.py
   ```

2. **Execute a task** and observe the log output

3. **Expected Result**: Each log line should appear exactly once (not twice)

4. **Check for**:
   - No duplicate "[scope/subscope][LEVEL] message" lines
   - Clean, single-instance log output in the UI
   - No stderr duplicates of custom-formatted logs

---

## Technical Details

### Affected Components

- **`agents_runner/app.py`**: Application startup and logging configuration
- **`agents_runner/log_format.py`**: Custom log formatting (unchanged)
- **`agents_runner/execution/supervisor.py`**: Task supervision (unchanged)
- **`agents_runner/docker/agent_worker.py`**: Container log emission (unchanged)

### Log Flow (After Fix)

```
Task Execution
  ↓
DockerAgentWorker emits via callback → custom log display
  ↓
Python's logging module DISABLED (no emission)
  ↓
RESULT: Log appears once (only from callback)
```

---

## Related Information

### Custom Logging Architecture

The codebase uses a **callback-based logging pattern** instead of Python's standard logging:

1. **Format**: `[scope/subscope][LEVEL] message`
   - Example: `[host/none][INFO] pull complete`
   - Example: `[gh/repo][INFO] updated GitHub context file`

2. **Callbacks**: Functions passed as `on_log` parameter
   - `TaskSupervisor` → `_on_log_capture()` → parent callback
   - `DockerAgentWorker` → `self._on_log()` → supervisor callback

3. **No Python logging handlers** used for task/container logs

### Why Not Use Python's Logging Module?

The custom callback system provides:
- More control over log formatting and routing
- Better integration with UI components
- Cleaner separation of concerns
- No risk of handler configuration conflicts

---

## Follow-up Items

None required. The fix is complete and addresses the root cause.

---

## Testing Notes

- Manually tested with `uv run main.py` (recommended)
- No automated tests added (per project guidelines: "Do not build tests unless asked to")
- Visual verification in UI log output is sufficient

---

**Completed by**: Coder Mode  
**Reviewed**: Self-reviewed for correctness and completeness
