# Task: Fix pyright errors in agents_runner/ui/dialogs/github_workroom_dialog.py

## File
File: `agents_runner/ui/dialogs/github_workroom_dialog.py`
Lines: 582, 583, 585

## Category
`qt-enum-QMessageBox`

## Errors
```
  Line 582: Cannot access attribute "Yes" for class "type[QMessageBox]"
  Line 582: Cannot access attribute "No" for class "type[QMessageBox]"
  Line 583: Cannot access attribute "No" for class "type[QMessageBox]"
  Line 585: Cannot access attribute "Yes" for class "type[QMessageBox]"
```

## Fix
Replace Qt5-style enum access with PySide6-style scoped enums:
- `Yes` -> `QMessageBox.StandardButton.Yes`  (2 occurrence(s))
- `No` -> `QMessageBox.StandardButton.No`  (2 occurrence(s))


## Verification
```bash
uv run pyright agents_runner/ui/dialogs/github_workroom_dialog.py
```
