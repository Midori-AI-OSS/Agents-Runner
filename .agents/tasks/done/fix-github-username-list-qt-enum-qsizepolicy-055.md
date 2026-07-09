# Task: Fix pyright errors in agents_runner/ui/pages/github_username_list.py

## File
File: `agents_runner/ui/pages/github_username_list.py`
Lines: 51

## Category
`qt-enum-QSizePolicy`

## Errors
```
  Line 51: Cannot access attribute "Expanding" for class "type[QSizePolicy]"
  Line 51: Cannot access attribute "Expanding" for class "type[QSizePolicy]"
```

## Fix
Replace Qt5-style enum access with PySide6-style scoped enums:
- `Expanding` -> `QSizePolicy.Policy.Expanding`  (2 occurrence(s))


## Verification
```bash
uv run pyright agents_runner/ui/pages/github_username_list.py
```
