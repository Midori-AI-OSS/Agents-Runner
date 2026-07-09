# Task: Fix pyright errors in agents_runner/ui/pages/environments_ports.py

## File
File: `agents_runner/ui/pages/environments_ports.py`
Lines: 136

## Category
`qt-enum-QTableWidget`

## Errors
```
  Line 136: Cannot access attribute "NoSelection" for class "type[QTableWidget]"
```

## Fix
Replace Qt5-style enum access with PySide6-style scoped enums:
- `NoSelection` -> `QAbstractItemView.SelectionMode.NoSelection`  (1 occurrence(s))
Required import: add `from PySide6.QtWidgets import QAbstractItemView` (not currently imported).
Alternatively, `QTableWidget.SelectionMode.NoSelection` works since QTableWidget inherits from QAbstractItemView and avoids the extra import.


## Verification
```bash
uv run pyright agents_runner/ui/pages/environments_ports.py
```
