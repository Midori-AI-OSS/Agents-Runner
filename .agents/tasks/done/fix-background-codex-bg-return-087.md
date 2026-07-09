# Task: Fix pyright errors in agents_runner/ui/themes/codex/background.py

## File
File: `agents_runner/ui/themes/codex/background.py`
Lines: 424

## Category
`codex-bg-return`

## Errors
```
  Line 424: Type "tuple[QLinearGradient, int, QColor | None, QColor | None]" is not assignable to return type "tuple[QLinearGradient, int, QColor, QColor]"
```

## Fix
Return type contains `QColor | None` but expects `QColor`.
Provide defaults for None values or change return type annotation.

## Verification
```bash
uv run pyright agents_runner/ui/themes/codex/background.py
```
