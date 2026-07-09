# Task: Fix pyright errors in agents_runner/ui/main_window_settings.py

## File
File: `agents_runner/ui/main_window_settings.py`
Lines: 428

## Category
`object-to-int`

## Errors
```
  Line 428: Argument of type "object" cannot be assigned to parameter "x" of type "ConvertibleToInt" in function "__new__"
  Line 428: Argument of type "object" cannot be assigned to parameter "x" of type "ConvertibleToInt" in function "__new__"
```

## Fix
Cast `object` values to `int` before passing to functions expecting int.
Use `int(value)` or add a type guard.
Lines affected: [428]

## Verification
```bash
uv run pyright agents_runner/ui/main_window_settings.py
```
