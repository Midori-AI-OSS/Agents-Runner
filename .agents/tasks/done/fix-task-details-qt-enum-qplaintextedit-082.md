# Task: Fix pyright errors in agents_runner/ui/pages/task_details.py

## File
File: `agents_runner/ui/pages/task_details.py`
Lines: 131

## Category
`qt-enum-QPlainTextEdit`

## Errors
```
  Line 131: Cannot access attribute "NoWrap" for class "type[QPlainTextEdit]"
```

## Fix
Replace Qt5-style enum access with PySide6-style scoped enums:
- `NoWrap` -> `QPlainTextEdit.LineWrapMode.NoWrap`  (1 occurrence(s))


## Verification
```bash
uv run pyright agents_runner/ui/pages/task_details.py
```
