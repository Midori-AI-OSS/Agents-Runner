# Task: Fix pyright errors in agents_runner/ui/pages/new_task.py

## File
File: `agents_runner/ui/pages/new_task.py`
Lines: 429

## Category
`newtask-interactive-slot`

## Errors
```
  Line 429: Cannot assign to attribute "_current_interactive_slot" for class "NewTaskPage*"
```

## Fix
`_current_interactive_slot` is typed as `Callable[..., Any] | None` (line 92) but line 429 assigns `new_slot` (typed `object`).
Use `cast(Callable[..., Any], new_slot)` when assigning (line 429):
```
self._current_interactive_slot = cast(Callable[..., Any], new_slot)
```
`Callable` is already imported at line 4 (`from typing import Any, Callable`).
Add `from typing import cast` to the imports.

## Verification
```bash
uv run pyright agents_runner/ui/pages/new_task.py
```
