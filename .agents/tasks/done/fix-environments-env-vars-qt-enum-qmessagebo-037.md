# Task: Fix pyright errors in agents_runner/ui/pages/environments_env_vars.py

## File
File: `agents_runner/ui/pages/environments_env_vars.py`
Lines: 210, 211, 213

## Category
`qt-enum-QMessageBox`

## Errors
```
  Line 210: Cannot access attribute "Yes" for class "type[QMessageBox]"
  Line 210: Cannot access attribute "No" for class "type[QMessageBox]"
  Line 211: Cannot access attribute "No" for class "type[QMessageBox]"
  Line 213: Cannot access attribute "Yes" for class "type[QMessageBox]"
```

## Fix
Replace Qt5-style enum access with PySide6-style scoped enums:
- `Yes` -> `QMessageBox.StandardButton.Yes`  (2 occurrence(s))
- `No` -> `QMessageBox.StandardButton.No`  (2 occurrence(s))


## Verification
```bash
uv run pyright agents_runner/ui/pages/environments_env_vars.py
```
