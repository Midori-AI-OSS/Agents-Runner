# Task: Fix pyright errors in agents_runner/ui/themes/copilot/background.py

## File
File: `agents_runner/ui/themes/copilot/background.py`
Lines: 72

## Category
`qt-enum-QFontDatabase`

## Errors
```
  Line 72: Cannot access attribute "FixedFont" for class "type[QFontDatabase]"
```

## Fix
Replace Qt5-style enum access with PySide6-style scoped enums:
- `FixedFont` -> `QFontDatabase.SystemFont.FixedFont`  (1 occurrence(s))


## Verification
```bash
uv run pyright agents_runner/ui/themes/copilot/background.py
```
