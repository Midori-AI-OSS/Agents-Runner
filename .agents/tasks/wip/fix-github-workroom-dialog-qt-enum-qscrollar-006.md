# Task: Fix pyright errors in agents_runner/ui/dialogs/github_workroom_dialog.py

## File
File: `agents_runner/ui/dialogs/github_workroom_dialog.py`
Lines: 135

## Category
`qt-enum-QScrollArea`

## Errors
```
  Line 135: Cannot access attribute "NoFrame" for class "type[QScrollArea]"
```

## Fix
Replace Qt5-style enum access with PySide6-style scoped enums:
- `NoFrame` -> `QFrame.Shape.NoFrame (also add `from PySide6.QtWidgets import QFrame` if not already imported)`  (1 occurrence(s))


## Verification
```bash
uv run pyright agents_runner/ui/dialogs/github_workroom_dialog.py
```
