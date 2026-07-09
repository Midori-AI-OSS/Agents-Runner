# Task: Fix pyright errors in agents_runner/ui/main_window_settings.py

## File
File: `agents_runner/ui/main_window_settings.py`
Lines: 124, 134, 157, 247, 282, 929, 935, 940

## Category
`mixin-cast-qwidget`

## Errors
```
  Line 124: Argument of type "Self@MainWindowSettingsMixin" cannot be assigned to parameter "parent" of type "QWidget | None" in function "information"
  Line 134: Argument of type "Self@MainWindowSettingsMixin" cannot be assigned to parameter "parent" of type "QWidget | None" in function "question"
  Line 157: Argument of type "Self@MainWindowSettingsMixin" cannot be assigned to parameter "parent" of type "QWidget | None" in function "information"
  Line 247: Argument of type "Self@MainWindowSettingsMixin" cannot be assigned to parameter "parent" of type "QWidget | None" in function "__init__"
  Line 282: Argument of type "Self@MainWindowSettingsMixin" cannot be assigned to parameter "parent" of type "QWidget | None" in function "information"
  Line 929: Argument of type "Self@MainWindowSettingsMixin" cannot be assigned to parameter "parent" of type "QWidget | None" in function "warning"
  Line 935: Argument of type "Self@MainWindowSettingsMixin" cannot be assigned to parameter "parent" of type "QWidget | None" in function "warning"
  Line 940: Argument of type "Self@MainWindowSettingsMixin" cannot be assigned to parameter "parent" of type "QWidget | None" in function "warning"
```

## Fix
Wrap `self` with `cast(QWidget, self)` when passing to functions expecting QWidget.
Import: add `from typing import cast` if not present.
Lines affected: [124, 134, 157, 247, 282, 929, 935, 940]

## Verification
```bash
uv run pyright agents_runner/ui/main_window_settings.py
```
