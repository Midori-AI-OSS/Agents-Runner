# Task: Fix pyright errors in agents_runner/ui/dialogs/auto_review_branch_dialog.py

## File
File: `agents_runner/ui/dialogs/auto_review_branch_dialog.py`
Lines: 59, 62

## Category
`qt-enum-QDialogButtonBox`

## Errors
```
  Line 59: Cannot access attribute "Ok" for class "type[QDialogButtonBox]"
  Line 59: Cannot access attribute "Cancel" for class "type[QDialogButtonBox]"
  Line 62: Cannot access attribute "Ok" for class "type[QDialogButtonBox]"
```

## Fix
Replace Qt5-style enum access with PySide6-style scoped enums:
- `Ok` -> `QDialogButtonBox.StandardButton.Ok`  (2 occurrence(s))
- `Cancel` -> `QDialogButtonBox.StandardButton.Cancel`  (1 occurrence(s))


## Verification
```bash
uv run pyright agents_runner/ui/dialogs/auto_review_branch_dialog.py
```
