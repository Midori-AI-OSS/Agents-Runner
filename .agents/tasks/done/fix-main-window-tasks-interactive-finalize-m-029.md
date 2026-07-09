# Task: Fix pyright errors in agents_runner/ui/main_window_tasks_interactive_finalize.py

## File
File: `agents_runner/ui/main_window_tasks_interactive_finalize.py`
Lines: 135

## Category
`mixin-cast-qwidget`

## Errors
```
  Line 135: Argument of type "Self@MainWindowTasksInteractiveFinalizeMixin" cannot be assigned to parameter "parent" of type "QWidget | None" in function "question"
```

## Fix
Wrap `self` with `cast(QWidget, self)` when passing to functions expecting QWidget.
Import: add `from typing import cast` if not present.
Lines affected: [135]

## Verification
```bash
uv run pyright agents_runner/ui/main_window_tasks_interactive_finalize.py
```
