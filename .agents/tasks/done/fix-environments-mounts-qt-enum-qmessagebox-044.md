# Task: Fix pyright errors in agents_runner/ui/pages/environments_mounts.py

## File
File: `agents_runner/ui/pages/environments_mounts.py`
Lines: 258, 259, 261

## Category
`qt-enum-QMessageBox`

## Errors
```
  Line 258: Cannot access attribute "Yes" for class "type[QMessageBox]"
  Line 258: Cannot access attribute "No" for class "type[QMessageBox]"
  Line 259: Cannot access attribute "No" for class "type[QMessageBox]"
  Line 261: Cannot access attribute "Yes" for class "type[QMessageBox]"
```

## Fix
Replace Qt5-style enum access with PySide6-style scoped enums:
- `Yes` -> `QMessageBox.StandardButton.Yes`  (2 occurrence(s))
- `No` -> `QMessageBox.StandardButton.No`  (2 occurrence(s))


## Verification
```bash
uv run pyright agents_runner/ui/pages/environments_mounts.py
```
