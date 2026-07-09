# Task: Fix pyright errors in agents_runner/ui/pages/task_details.py

## File
File: `agents_runner/ui/pages/task_details.py`
Lines: 84

## Category
`qt-enum-QToolButton`

## Errors
```
  Line 84: Cannot access attribute "InstantPopup" for class "type[QToolButton]"
```

## Fix
Replace Qt5-style enum access with PySide6-style scoped enums:
- `InstantPopup` -> `QToolButton.ToolButtonPopupMode.InstantPopup`  (1 occurrence(s))


## Verification
```bash
uv run pyright agents_runner/ui/pages/task_details.py
```
