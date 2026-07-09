# Task: Fix pyright errors in agents_runner/ui/widgets/glass_card.py

## File
File: `agents_runner/ui/widgets/glass_card.py`
Lines: 12

## Category
`qt-enum-QFrame`

## Errors
```
  Line 12: Cannot access attribute "NoFrame" for class "type[QFrame]"
```

## Fix
Replace Qt5-style enum access with PySide6-style scoped enums:
- `NoFrame` -> `QFrame.Shape.NoFrame`  (1 occurrence(s))


## Verification
```bash
uv run pyright agents_runner/ui/widgets/glass_card.py
```
