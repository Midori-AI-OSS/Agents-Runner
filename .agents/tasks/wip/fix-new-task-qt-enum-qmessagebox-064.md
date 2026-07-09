# Task: Fix pyright errors in agents_runner/ui/pages/new_task.py

## File
File: `agents_runner/ui/pages/new_task.py`
Lines: 331, 332, 335

## Category
`qt-enum-QMessageBox`

## Errors
```
  Line 331: Cannot access attribute "Yes" for class "type[QMessageBox]"
  Line 331: Cannot access attribute "No" for class "type[QMessageBox]"
  Line 332: Cannot access attribute "No" for class "type[QMessageBox]"
  Line 335: Cannot access attribute "Yes" for class "type[QMessageBox]"
```

## Fix
Replace Qt5-style enum access with PySide6-style scoped enums:
- `Yes` -> `QMessageBox.StandardButton.Yes`  (2 occurrence(s))
- `No` -> `QMessageBox.StandardButton.No`  (2 occurrence(s))


## Verification
```bash
uv run pyright agents_runner/ui/pages/new_task.py
```
