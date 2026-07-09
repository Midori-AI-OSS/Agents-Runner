# Task: Fix pyright errors in agents_runner/ui/pages/environments_mounts.py

## File
File: `agents_runner/ui/pages/environments_mounts.py`
Lines: 89, 90, 91, 92

## Category
`qt-enum-QHeaderView`

## Errors
```
  Line 89: Cannot access attribute "Stretch" for class "type[QHeaderView]"
  Line 90: Cannot access attribute "Stretch" for class "type[QHeaderView]"
  Line 91: Cannot access attribute "ResizeToContents" for class "type[QHeaderView]"
  Line 92: Cannot access attribute "ResizeToContents" for class "type[QHeaderView]"
```

## Fix
Replace Qt5-style enum access with PySide6-style scoped enums:
- `Stretch` -> `QHeaderView.ResizeMode.Stretch`  (2 occurrence(s))
- `ResizeToContents` -> `QHeaderView.ResizeMode.ResizeToContents`  (2 occurrence(s))


## Verification
```bash
uv run pyright agents_runner/ui/pages/environments_mounts.py
```
