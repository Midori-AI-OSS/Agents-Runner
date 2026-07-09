# Task: Fix pyright errors in agents_runner/ui/pages/environments_ports.py

## File
File: `agents_runner/ui/pages/environments_ports.py`
Lines: 130, 131, 132

## Category
`qt-enum-QHeaderView`

## Errors
```
  Line 130: Cannot access attribute "Stretch" for class "type[QHeaderView]"
  Line 131: Cannot access attribute "Stretch" for class "type[QHeaderView]"
  Line 132: Cannot access attribute "ResizeToContents" for class "type[QHeaderView]"
```

## Fix
Replace Qt5-style enum access with PySide6-style scoped enums:
- `Stretch` -> `QHeaderView.ResizeMode.Stretch`  (2 occurrence(s))
- `ResizeToContents` -> `QHeaderView.ResizeMode.ResizeToContents`  (1 occurrence(s))


## Verification
```bash
uv run pyright agents_runner/ui/pages/environments_ports.py
```
