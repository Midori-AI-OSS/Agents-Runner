# Task: Fix pyright errors in agents_runner/ui/pages/environments_ports.py

## File
File: `agents_runner/ui/pages/environments_ports.py`
Lines: 326, 327, 329

## Category
`qt-enum-QMessageBox`

## Errors
```
  Line 326: Cannot access attribute "Yes" for class "type[QMessageBox]"
  Line 326: Cannot access attribute "No" for class "type[QMessageBox]"
  Line 327: Cannot access attribute "No" for class "type[QMessageBox]"
  Line 329: Cannot access attribute "Yes" for class "type[QMessageBox]"
```

## Fix
Replace Qt5-style enum access with PySide6-style scoped enums:
- `Yes` -> `QMessageBox.StandardButton.Yes`  (2 occurrence(s))
- `No` -> `QMessageBox.StandardButton.No`  (2 occurrence(s))


## Verification
```bash
uv run pyright agents_runner/ui/pages/environments_ports.py
```
