# Task: Fix pyright errors in agents_runner/ui/main_window_tasks_interactive.py

## File
File: `agents_runner/ui/main_window_tasks_interactive.py`
Lines: 61, 93, 102, 110, 121, 135, 139, 215, 254, 260

## Category
`mixin-cast-qwidget`

## Errors
```
  Line 61: Argument of type "Self@MainWindowTasksInteractiveMixin" cannot be assigned to parameter "parent" of type "QWidget | None" in function "__init__"
  Line 93: Argument of type "Self@MainWindowTasksInteractiveMixin" cannot be assigned to parameter "parent" of type "QWidget | None" in function "critical"
  Line 102: Argument of type "Self@MainWindowTasksInteractiveMixin" cannot be assigned to parameter "parent" of type "QWidget | None" in function "warning"
  Line 110: Argument of type "Self@MainWindowTasksInteractiveMixin" cannot be assigned to parameter "parent" of type "QWidget | None" in function "warning"
  Line 121: Argument of type "Self@MainWindowTasksInteractiveMixin" cannot be assigned to parameter "parent" of type "QWidget" in function "resolve_launch_port_decision"
  Line 135: Argument of type "Self@MainWindowTasksInteractiveMixin" cannot be assigned to parameter "parent" of type "QWidget | None" in function "warning"
  Line 139: Argument of type "Self@MainWindowTasksInteractiveMixin" cannot be assigned to parameter "parent" of type "QWidget | None" in function "warning"
  Line 215: Argument of type "Self@MainWindowTasksInteractiveMixin" cannot be assigned to parameter "parent" of type "QWidget | None" in function "warning"
  Line 254: Argument of type "Self@MainWindowTasksInteractiveMixin" cannot be assigned to parameter "parent" of type "QWidget | None" in function "warning"
  Line 260: Argument of type "Self@MainWindowTasksInteractiveMixin" cannot be assigned to parameter "parent" of type "QWidget | None" in function "warning"
```

## Fix
Wrap `self` with `cast(QWidget, self)` when passing to functions expecting QWidget.
Import: add `from typing import cast` if not present.
Lines affected: [61, 93, 102, 110, 121, 135, 139, 215, 254, 260]

## Verification
```bash
uv run pyright agents_runner/ui/main_window_tasks_interactive.py
```
