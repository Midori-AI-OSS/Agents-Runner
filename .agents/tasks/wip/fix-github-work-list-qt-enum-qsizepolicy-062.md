# Task: Fix pyright errors in agents_runner/ui/pages/github_work_list.py

## File
File: `agents_runner/ui/pages/github_work_list.py`
Lines: 60, 75, 226

## Category
`qt-enum-QSizePolicy`

## Errors
```
  Line 60: Cannot access attribute "Expanding" for class "type[QSizePolicy]"
  Line 60: Cannot access attribute "Fixed" for class "type[QSizePolicy]"
  Line 75: Cannot access attribute "Fixed" for class "type[QSizePolicy]"
  Line 75: Cannot access attribute "Expanding" for class "type[QSizePolicy]"
  Line 226: Cannot access attribute "Expanding" for class "type[QSizePolicy]"
  Line 226: Cannot access attribute "Fixed" for class "type[QSizePolicy]"
```

## Fix
Replace Qt5-style enum access with PySide6-style scoped enums:
- `Expanding` -> `QSizePolicy.Policy.Expanding`  (3 occurrence(s))
- `Fixed` -> `QSizePolicy.Policy.Fixed`  (3 occurrence(s))


## Verification
```bash
uv run pyright agents_runner/ui/pages/github_work_list.py
```
