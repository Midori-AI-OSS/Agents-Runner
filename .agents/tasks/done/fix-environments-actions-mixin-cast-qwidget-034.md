# Task: Fix pyright errors in agents_runner/ui/pages/environments_actions.py

## File
File: `agents_runner/ui/pages/environments_actions.py`
Lines: 88, 98, 164, 206, 213, 225, 389, 394, 402

## Category
`mixin-cast-qwidget`

## Errors
```
  Line 88: Argument of type "Self@EnvironmentsPageActionsMixin" cannot be assigned to parameter "parent" of type "QWidget | None" in function "__init__"
  Line 98: Argument of type "Self@EnvironmentsPageActionsMixin" cannot be assigned to parameter "parent" of type "QWidget | None" in function "question"
  Line 164: Argument of type "Self@EnvironmentsPageActionsMixin" cannot be assigned to parameter "parent" of type "QWidget | None" in function "warning"
  Line 206: Argument of type "Self@EnvironmentsPageActionsMixin" cannot be assigned to parameter "parent" of type "QWidget | None" in function "warning"
  Line 213: Argument of type "Self@EnvironmentsPageActionsMixin" cannot be assigned to parameter "parent" of type "QWidget | None" in function "warning"
  Line 225: Argument of type "Self@EnvironmentsPageActionsMixin" cannot be assigned to parameter "parent" of type "QWidget | None" in function "warning"
  Line 389: Argument of type "Self@EnvironmentsPageActionsMixin" cannot be assigned to parameter "parent" of type "QWidget | None" in function "warning"
  Line 394: Argument of type "Self@EnvironmentsPageActionsMixin" cannot be assigned to parameter "parent" of type "QWidget | None" in function "warning"
  Line 402: Argument of type "Self@EnvironmentsPageActionsMixin" cannot be assigned to parameter "parent" of type "QWidget | None" in function "warning"
```

## Fix
Wrap `self` with `cast(QWidget, self)` when passing to functions expecting QWidget.
`cast` is already imported (`from typing import TYPE_CHECKING, cast`), but `QWidget` is not.
Add import: `from PySide6.QtWidgets import QWidget`.
Lines affected: [88, 98, 164, 206, 213, 225, 389, 394, 402]

## Verification
```bash
uv run pyright agents_runner/ui/pages/environments_actions.py
```
