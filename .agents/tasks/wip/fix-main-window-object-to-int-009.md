# Task: Fix pyright errors in agents_runner/ui/main_window.py

## File
File: `agents_runner/ui/main_window.py`
Lines: 607

## Category
`object-to-int`

## Errors
```
  Line 607: Argument of type "object" cannot be assigned to parameter "x" of type "ConvertibleToInt" in function "__new__"
  Line 607: Argument of type "object" cannot be assigned to parameter "x" of type "ConvertibleToInt" in function "__new__"
```

## Fix
Cast `object` values to `int` before passing to functions expecting int.
Use `int(value)` or add a type guard.
Lines affected: [607]

## Verification
```bash
uv run pyright agents_runner/ui/main_window.py
```
