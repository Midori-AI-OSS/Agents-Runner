# Task: Fix pyright errors in agents_runner/ui/pages/new_task.py

## File
File: `agents_runner/ui/pages/new_task.py`
Lines: 1397

## Category
`qt-enum-QTextCursor`

## Errors
```
  Line 1397: Cannot access attribute "End" for class "type[QTextCursor]"
```

## Fix
`QTextCursor.MoveMode.End` is wrong -- `QTextCursor.MoveMode` only has `MoveAnchor` and `KeepAnchor` in PySide6.
The correct enum is `QTextCursor.MoveOperation.End`, since `movePosition()` takes a `MoveOperation`.

Changes needed:
- `QTextCursor.End` -> `QTextCursor.MoveOperation.End` (1 occurrence on line 1397)
No new import is needed -- `QTextCursor` is already imported from `PySide6.QtGui` on line 17.

## Verification
```bash
uv run pyright agents_runner/ui/pages/new_task.py
```
