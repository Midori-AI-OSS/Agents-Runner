# Task: Fix pyright errors in agents_runner/ui/widgets/chat_bubble.py

## File
File: `agents_runner/ui/widgets/chat_bubble.py`
Lines: 134, 211

## Category
`qt-enum-QSizePolicy`

## Errors
```
  Line 134: Cannot access attribute "Expanding" for class "type[QSizePolicy]"
  Line 134: Cannot access attribute "Minimum" for class "type[QSizePolicy]"
  Line 211: Cannot access attribute "Expanding" for class "type[QSizePolicy]"
  Line 211: Cannot access attribute "Minimum" for class "type[QSizePolicy]"
```

## Fix
Replace Qt5-style enum access with PySide6-style scoped enums:
- `Expanding` -> `QSizePolicy.Policy.Expanding`  (2 occurrence(s))
- `Minimum` -> `QSizePolicy.Policy.Minimum`  (2 occurrence(s))


## Verification
```bash
uv run pyright agents_runner/ui/widgets/chat_bubble.py
```
