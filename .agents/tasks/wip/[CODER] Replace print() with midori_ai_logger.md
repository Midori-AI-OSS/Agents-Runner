# Task: Replace print() Calls with Structured Logging

## Goal

Improve logging hygiene by replacing `print()` statements with `midori_ai_logger` structured logging, following AGENTS.md guidance.

## Rule Reference

**AGENTS.md Section:** "Logging"
> "Avoid `print()` for non-CLI output (exceptions: fatal startup/diagnostics paths); use structured logging instead."

**Violation:** 36+ `print()` calls throughout codebase, particularly in STT and task interactive modules.

## Scope

- Replace print() with `midori_ai_logger` in high-volume areas
- Focus on `ui/pages/new_task.py` (18 print calls - STT logging)
- Focus on `ui/main_window_tasks_interactive.py` (5 print calls)
- Replace debug print() in `ui/desktop_viewer/app.py` and `ui/pages/artifacts_tab.py`
- Keep only fatal/diagnostics print() where justified

## Non-Goals

- Do not remove print() from `diagnostics/crash_reporting.py` (emergency output)
- Do not change print() that outputs to stderr for Qt diagnostics (if justified)
- Do not change the logging behavior of `ui/runtime/app.py` cleanup warnings (defer)
- Do not add new logging features

## Exceptions (print() Allowed to Remain)

- `agents_runner/diagnostics/crash_reporting.py`: Emergency crash output
- `agents_runner/ui/qt_diagnostics.py`: Qt diagnostics to stderr (may be justified)
- `agents_runner/ui/runtime/app.py`: Startup/cleanup messages (defer to separate task)

## Affected Files Inventory

**High Priority (Must Fix):**
- `agents_runner/ui/pages/new_task.py`: 18 print() calls (STT logging)
- `agents_runner/ui/main_window_tasks_interactive.py`: 5 print() calls

**Medium Priority:**
- `agents_runner/ui/desktop_viewer/app.py`: 3 print() calls (debug statements)
- `agents_runner/ui/pages/artifacts_tab.py`: 1 print() call

**Deferred (Diagnostics/Startup):**
- `agents_runner/diagnostics/crash_reporting.py`: Keep as-is (emergency)
- `agents_runner/ui/qt_diagnostics.py`: Keep as-is (Qt diagnostics)
- `agents_runner/ui/runtime/app.py`: Keep as-is (startup/cleanup)

## Acceptance Criteria

- [ ] Import `midori_ai_logger` in affected modules
- [ ] Replace all print() in `ui/pages/new_task.py` with logger calls
- [ ] Replace all print() in `ui/main_window_tasks_interactive.py` with logger calls
- [ ] Replace debug print() in `ui/desktop_viewer/app.py` with logger calls
- [ ] Replace print() in `ui/pages/artifacts_tab.py` with logger call
- [ ] Logger uses appropriate levels (debug, info, warning, error)
- [ ] `uv run ruff format .` passes
- [ ] `uv run ruff check .` passes
- [ ] Verification command shows <10 print() calls remaining (only exceptions)

## Verification Commands

**Before changes (should fail):**
```bash
# Count print() calls
rg -n "\\bprint\\(" agents_runner | wc -l
# Expected: 36+

# High-volume areas
rg -n "\\bprint\\(" agents_runner/ui/pages/new_task.py | wc -l
# Expected: 18

rg -n "\\bprint\\(" agents_runner/ui/main_window_tasks_interactive.py | wc -l
# Expected: 5
```

**After changes (should pass):**
```bash
# Count remaining print() calls (should be <10, only exceptions)
rg -n "\\bprint\\(" agents_runner | wc -l
# Expected: <10

# Verify logger usage in fixed files
rg -n "from midori_ai_logger import\|logger\\.(debug|info|warning|error)" agents_runner/ui/pages/new_task.py
# Expected: Multiple matches

rg -n "from midori_ai_logger import\|logger\\.(debug|info|warning|error)" agents_runner/ui/main_window_tasks_interactive.py
# Expected: Multiple matches

# Remaining prints should only be in exception files
rg -n "\\bprint\\(" agents_runner --glob '!agents_runner/diagnostics/**' --glob '!agents_runner/ui/qt_diagnostics.py' --glob '!agents_runner/ui/runtime/app.py'
# Expected: <5 matches
```

## Implementation Pattern

**Before (using print):**
```python
print("[STT] Starting voice recording")
print(f"[STT] Recorder error: {exc}")
```

**After (using logger):**
```python
from midori_ai_logger import get_logger

logger = get_logger(__name__)

logger.info("Starting voice recording", extra={"component": "STT"})
logger.error("Recorder error", exc_info=exc, extra={"component": "STT"})
```

**Log Level Guidelines:**
- `logger.debug()`: Verbose diagnostic info (STT lifecycle events)
- `logger.info()`: Normal operational messages (STT start/stop)
- `logger.warning()`: Warning conditions (cleanup failures)
- `logger.error()`: Error conditions (STT errors, file operations failed)

## Priority Order

1. **First:** `ui/pages/new_task.py` (18 calls, high volume)
2. **Second:** `ui/main_window_tasks_interactive.py` (5 calls)
3. **Third:** `ui/desktop_viewer/app.py` (3 calls)
4. **Fourth:** `ui/pages/artifacts_tab.py` (1 call)

## Definition of Done

- All acceptance criteria checked
- All verification commands pass
- Committed with message: `[REFACTOR] Replace print() with midori_ai_logger in UI modules`
- Version bumped in `pyproject.toml` (TASK +1)
