# Task: Fix pyright errors in agents_runner/ui/pages/dashboard_row.py

## File
File: `agents_runner/ui/pages/dashboard_row.py`
Lines: 76

## Category
`qt-enum-QSizePolicy`

## Errors
```
  Line 76: Cannot access attribute "Expanding" for class "type[QSizePolicy]"
  Line 76: Cannot access attribute "Fixed" for class "type[QSizePolicy]"
```

## Fix
Replace Qt5-style enum access with PySide6-style scoped enums:
- `Expanding` -> `QSizePolicy.Policy.Expanding`  (1 occurrence(s))
- `Fixed` -> `QSizePolicy.Policy.Fixed`  (1 occurrence(s))


## Verification
```bash
uv run pyright agents_runner/ui/pages/dashboard_row.py
```
