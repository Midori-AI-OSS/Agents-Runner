# Task: Fix pyright errors in agents_runner/ui/pages/environments_actions.py

## File
File: `agents_runner/ui/pages/environments_actions.py`
Lines: 101, 102, 104

## Category
`qt-enum-QMessageBox`

## Errors
```
  Line 101: Cannot access attribute "Yes" for class "type[QMessageBox]"
  Line 101: Cannot access attribute "No" for class "type[QMessageBox]"
  Line 102: Cannot access attribute "No" for class "type[QMessageBox]"
  Line 104: Cannot access attribute "Yes" for class "type[QMessageBox]"
```

## Fix
Replace Qt5-style enum access with PySide6-style scoped enums:
- `Yes` -> `QMessageBox.StandardButton.Yes`  (2 occurrence(s))
- `No` -> `QMessageBox.StandardButton.No`  (2 occurrence(s))


## Verification
```bash
uv run pyright agents_runner/ui/pages/environments_actions.py
```
