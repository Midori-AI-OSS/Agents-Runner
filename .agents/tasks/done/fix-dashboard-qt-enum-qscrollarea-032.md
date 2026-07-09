# Task: Fix pyright errors in agents_runner/ui/pages/dashboard.py

## File
File: `agents_runner/ui/pages/dashboard.py`
Lines: 192, 212

## Category
`qt-enum-QScrollArea`

## Errors
```
  Line 192: Cannot access attribute "NoFrame" for class "type[QScrollArea]"
  Line 212: Cannot access attribute "NoFrame" for class "type[QScrollArea]"
```

## Fix
Replace Qt5-style enum access with PySide6-style scoped enums:
- `NoFrame` -> `QFrame.Shape.NoFrame (also add `from PySide6.QtWidgets import QFrame` if not already imported)`  (2 occurrence(s))


## Verification
```bash
uv run pyright agents_runner/ui/pages/dashboard.py
```
