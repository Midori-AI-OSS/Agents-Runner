# Task 02: Staging Directory Cleanup

## Summary

Ensure that per-task artifact staging directories under `~/.midoriai/agents-runner/artifacts/<task_id>/staging/` are cleaned up after finalization and at startup for orphaned tasks, preventing disk accumulation.

## File Changed (1)

### agents_runner/ui/main_window_task_recovery.py

**1. Add `import shutil`.** Insert after `import time` (currently line 6):

Current import block (lines 1-31):
```python
from __future__ import annotations

import os
import subprocess
import threading
import time

from itertools import chain
...
from agents_runner.ui.utils import stain_color
```

Add `import shutil` after `import time`:
```python
import os
import shutil
import subprocess
import threading
import time
```

**2. Update the `artifacts` import line (originally line 16; shifts to line 17 after step 1).** Change from:
```python
from agents_runner.artifacts import collect_artifacts_from_container_with_timeout
```
To two separate imports:
```python
from agents_runner.artifacts import get_staging_dir
from agents_runner.artifacts import collect_artifacts_from_container_with_timeout
```

**3. Add `finally` block to `_finalize_task_worker` method.** Insert after the `except Exception` block (after line 699), still inside `_finalize_task_worker`:

```python
        finally:
            try:
                staging_dir = get_staging_dir(task_id)
                shutil.rmtree(staging_dir, ignore_errors=True)
            except Exception:
                pass
```

**Indentation:** The `finally` must be at the same indentation level as `try:` and `except Exception` within `_finalize_task_worker`. The `try`/`except` inside the `finally` is indented one level deeper.

**4. Add orphan staging sweep to `_reconcile_tasks_after_restart`.** Insert after the `for` loop ends (after line 87) and before `_tick_recovery` (line 89). This code goes inside `_reconcile_tasks_after_restart`:

```python
        # Orphan staging sweep: remove leftover staging directories for finished tasks.
        for task in list(self._tasks.values()):
            if task.is_active():
                continue
            task_id_sweep = str(task.task_id or "").strip()
            if not task_id_sweep:
                continue
            finalization_lower = (task.finalization_state or "").lower().strip()
            if finalization_lower in {"pending", "running"}:
                continue
            existing = self._finalization_threads.get(task_id_sweep)
            if existing is not None and existing.is_alive():
                continue
            if not (task.is_done() or task.is_failed()):
                continue
            try:
                staging_dir = get_staging_dir(task_id_sweep)
                shutil.rmtree(staging_dir, ignore_errors=True)
            except Exception:
                pass
```

## Guard Logic Explanation

The orphan staging sweep in `_reconcile_tasks_after_restart` uses multiple guard conditions to avoid removing staging for tasks that may still produce artifacts:

1. **`task.is_active()`** — Skip running tasks whose stage hasn't completed.
2. **Empty task_id** — Skip tasks that don't have a task_id yet.
3. **`finalization_state in {"pending", "running"}`** — Skip tasks that are queued or actively finalizing; artifacts collection hasn't finished yet.
4. **Live finalization thread check** — Even if `finalization_state` is something unexpected, check if a live thread exists for this task_id.
5. **`task.is_done() or task.is_failed()`** — Only clean up staging for tasks that have reached a terminal state.

## `get_staging_dir` Reference

Defined in `agents_runner/artifacts.py` (line 596):
```python
def get_staging_dir(task_id: str) -> Path:
```

Returns `Path.home() / ".midoriai" / "agents-runner" / "artifacts" / task_id / "staging"`.

## Risk Assessment

- **Idempotent:** `shutil.rmtree(..., ignore_errors=True)` is safe to call on non-existent directories.
- **Protected:** Active and finalizing tasks are explicitly guarded.
- **No data loss:** Artifact collection into the permanent store (`~/.midoriai/agents-runner/artifacts/<task_id>/artifacts/`) completes before `finalization_state` transitions to `"done"`, so staging is only removed *after* collection succeeds (or after failure, in the `except` case, where staging is also cleaned up in the `finally` block).

## Pre-commit Validation

- Run `uv run ruff format .`
- Run `uv run ruff check .`
- Run `uv run basedpyright`
- Verify `uv run main.py` launches without import errors
