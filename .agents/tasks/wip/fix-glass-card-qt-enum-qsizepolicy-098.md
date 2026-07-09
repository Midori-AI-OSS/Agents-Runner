# Task: Fix pyright errors in agents_runner/ui/widgets/glass_card.py

## File
File: `agents_runner/ui/widgets/glass_card.py`
Lines: 13

## Category
`qt-enum-QSizePolicy`

## Errors
```
  Line 13: Cannot access attribute "Expanding" for class "type[QSizePolicy]"
  Line 13: Cannot access attribute "Preferred" for class "type[QSizePolicy]"
```

## Fix
Replace Qt5-style enum access with PySide6-style scoped enums:
- `Expanding` -> `QSizePolicy.Policy.Expanding`  (1 occurrence(s))
- `Preferred` -> `QSizePolicy.Policy.Preferred`  (1 occurrence(s))


## Verification
```bash
uv run pyright agents_runner/ui/widgets/glass_card.py
```
