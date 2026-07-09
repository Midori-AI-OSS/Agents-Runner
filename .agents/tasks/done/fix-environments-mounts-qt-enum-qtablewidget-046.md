# Task: Fix pyright errors in agents_runner/ui/pages/environments_mounts.py

## File
File: `agents_runner/ui/pages/environments_mounts.py`
Lines: 96

## Category
`qt-enum-QTableWidget`

## Errors
```
  Line 96: Cannot access attribute "NoSelection" for class "type[QTableWidget]"
```

## Fix
Replace Qt5-style enum access with PySide6-style scoped enums:
- `NoSelection` -> `QAbstractItemView.SelectionMode.NoSelection`  (1 occurrence(s))
Required import: add `from PySide6.QtWidgets import QAbstractItemView` (not currently imported).


## Verification
```bash
uv run pyright agents_runner/ui/pages/environments_mounts.py
```
