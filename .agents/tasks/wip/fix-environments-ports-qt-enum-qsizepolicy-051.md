# Task: Fix pyright errors in agents_runner/ui/pages/environments_ports.py

## File
File: `agents_runner/ui/pages/environments_ports.py`
Lines: 138

## Category
`qt-enum-QSizePolicy`

## Errors
```
  Line 138: Cannot access attribute "Expanding" for class "type[QSizePolicy]"
  Line 138: Cannot access attribute "Expanding" for class "type[QSizePolicy]"
```

## Fix
Replace Qt5-style enum access with PySide6-style scoped enums:
- `Expanding` -> `QSizePolicy.Policy.Expanding`  (2 occurrence(s))


## Verification
```bash
uv run pyright agents_runner/ui/pages/environments_ports.py
```
