# Task: Fix pyright errors in agents_runner/ui/graphics.py

## File
File: `agents_runner/ui/graphics.py`
Lines: 143

## Category
`object-to-str`

## Errors
```
  Line 143: Argument of type "object | None" cannot be assigned to parameter "theme_name" of type "str | None" in function "normalize_ui_theme_name"
```

## Fix
Cast `object | None` to `str | None` before passing to function.
Use `cast(str, value)` or add a type guard `if isinstance(value, str)`.

## Verification
```bash
uv run pyright agents_runner/ui/graphics.py
```
