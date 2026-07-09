# Task: Fix pyright errors in agents_runner/ui/pages/environments_prompts.py

## File
File: `agents_runner/ui/pages/environments_prompts.py`
Lines: 106, 107, 110

## Category
`qt-enum-QMessageBox`

## Errors
```
  Line 106: Cannot access attribute "Yes" for class "type[QMessageBox]"
  Line 106: Cannot access attribute "No" for class "type[QMessageBox]"
  Line 107: Cannot access attribute "No" for class "type[QMessageBox]"
  Line 110: Cannot access attribute "Yes" for class "type[QMessageBox]"
```

## Fix
Replace Qt5-style enum access with PySide6-style scoped enums:
- `Yes` -> `QMessageBox.StandardButton.Yes`  (2 occurrence(s))
- `No` -> `QMessageBox.StandardButton.No`  (2 occurrence(s))


## Verification
```bash
uv run pyright agents_runner/ui/pages/environments_prompts.py
```
