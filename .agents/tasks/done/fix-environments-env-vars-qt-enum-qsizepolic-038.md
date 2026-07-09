# Task: Fix pyright errors in agents_runner/ui/pages/environments_env_vars.py

## File
File: `agents_runner/ui/pages/environments_env_vars.py`
Lines: 72

## Category
`qt-enum-QSizePolicy`

## Errors
```
  Line 72: Cannot access attribute "Expanding" for class "type[QSizePolicy]"
  Line 72: Cannot access attribute "Expanding" for class "type[QSizePolicy]"
```

## Fix
Replace Qt5-style enum access with PySide6-style scoped enums:
- `Expanding` -> `QSizePolicy.Policy.Expanding`  (2 occurrence(s))


## Verification
```bash
uv run pyright agents_runner/ui/pages/environments_env_vars.py
```
