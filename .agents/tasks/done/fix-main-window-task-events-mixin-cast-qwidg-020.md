# Task: Fix pyright errors in agents_runner/ui/main_window_task_events.py

## File
File: `agents_runner/ui/main_window_task_events.py`
Lines: 76, 187, 193, 215

## Category
`mixin-cast-qwidget`

## Errors
```
  Line 76: Argument of type "Self@MainWindowTaskEventsMixin" cannot be assigned to parameter "parent" of type "QWidget | None" in function "information"
  Line 187: Argument of type "Self@MainWindowTaskEventsMixin" cannot be assigned to parameter "parent" of type "QWidget | None" in function "warning"
  Line 193: Argument of type "Self@MainWindowTaskEventsMixin" cannot be assigned to parameter "parent" of type "QWidget | None" in function "warning"
  Line 215: Argument of type "Self@MainWindowTaskEventsMixin" cannot be assigned to parameter "parent" of type "QWidget | None" in function "question"
```

## Fix
Wrap `self` with `cast(QWidget, self)` when passing to functions expecting QWidget.
Import: add `from typing import cast` if not present.
Lines affected: [76, 187, 193, 215]

## Verification
```bash
uv run pyright agents_runner/ui/main_window_task_events.py
```
