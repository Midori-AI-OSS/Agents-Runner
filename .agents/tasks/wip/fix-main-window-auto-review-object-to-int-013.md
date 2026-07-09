# Task: Fix pyright errors in agents_runner/ui/main_window_auto_review.py

## File
File: `agents_runner/ui/main_window_auto_review.py`
Lines: 128, 171

## Category
`object-to-int`

## Errors
```
  Line 128: Argument of type "object | Literal[0]" cannot be assigned to parameter "x" of type "ConvertibleToInt" in function "__new__"
  Line 128: Argument of type "object | Literal[0]" cannot be assigned to parameter "x" of type "ConvertibleToInt" in function "__new__"
  Line 171: Argument of type "object | Literal[0]" cannot be assigned to parameter "x" of type "ConvertibleToInt" in function "__new__"
  Line 171: Argument of type "object | Literal[0]" cannot be assigned to parameter "x" of type "ConvertibleToInt" in function "__new__"
```

## Fix
Cast `object` values to `int` before passing to functions expecting int.
Use `int(value)` or add a type guard.
Lines affected: [128, 171]

## Verification
```bash
uv run pyright agents_runner/ui/main_window_auto_review.py
```
