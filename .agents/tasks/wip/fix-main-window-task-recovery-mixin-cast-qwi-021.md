# Task: Fix pyright errors in agents_runner/ui/main_window_task_recovery.py

## File
File: `agents_runner/ui/main_window_task_recovery.py`
Lines: 246

## Category
`mixin-cast-qwidget`

## Errors
```
  Line 246: Argument of type "Self@MainWindowTaskRecoveryMixin" cannot be assigned to parameter "parent" of type "QWidget | None" in function "question"
```

## Fix
Wrap `self` with `cast(QWidget, self)` when passing to functions expecting QWidget.
Import: add `from typing import cast` if not present.
Lines affected: [246]

## Verification
```bash
uv run pyright agents_runner/ui/main_window_task_recovery.py
```
