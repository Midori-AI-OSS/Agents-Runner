# Task: Fix pyright errors in agents_runner/ui/main_window_preflight.py

## File
File: `agents_runner/ui/main_window_preflight.py`
Lines: 44, 48, 255

## Category
`mixin-cast-qwidget`

## Errors
```
  Line 44: Argument of type "Self@MainWindowPreflightMixin" cannot be assigned to parameter "parent" of type "QWidget | None" in function "critical"
  Line 48: Argument of type "Self@MainWindowPreflightMixin" cannot be assigned to parameter "parent" of type "QWidget | None" in function "warning"
  Line 255: Argument of type "Self@MainWindowPreflightMixin" cannot be assigned to parameter "parent" of type "QWidget | None" in function "warning"
```

## Fix
Wrap `self` with `cast(QWidget, self)` when passing to functions expecting QWidget.
Import: add `from typing import cast` if not present.
Lines affected: [44, 48, 255]

## Verification
```bash
uv run pyright agents_runner/ui/main_window_preflight.py
```
