# Task: Fix pyright errors in agents_runner/ui/pages/github_work_list.py

## File
File: `agents_runner/ui/pages/github_work_list.py`
Lines: 315

## Category
`qt-enum-QScrollArea`

## Errors
```
  Line 315: Cannot access attribute "NoFrame" for class "type[QScrollArea]"
```

## Fix
Replace Qt5-style enum access with PySide6-style scoped enums:
- `NoFrame` -> `QFrame.Shape.NoFrame (also add `from PySide6.QtWidgets import QFrame` if not already imported)`  (1 occurrence(s))


## Verification
```bash
uv run pyright agents_runner/ui/pages/github_work_list.py
```
