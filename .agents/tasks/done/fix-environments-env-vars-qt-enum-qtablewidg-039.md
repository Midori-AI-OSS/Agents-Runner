# Task: Fix pyright errors in agents_runner/ui/pages/environments_env_vars.py

## File
File: `agents_runner/ui/pages/environments_env_vars.py`
Lines: 70

## Category
`qt-enum-QTableWidget`

## Errors
```
  Line 70: Cannot access attribute "NoSelection" for class "type[QTableWidget]"
```

## Fix
Replace Qt5-style enum access with PySide6-style scoped enums:
- `NoSelection` -> `QAbstractItemView.SelectionMode.NoSelection`  (1 occurrence(s))
Required import: add `from PySide6.QtWidgets import QAbstractItemView` (not currently imported).


## Verification
```bash
uv run pyright agents_runner/ui/pages/environments_env_vars.py
```
