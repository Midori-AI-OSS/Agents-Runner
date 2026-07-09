# Task: Fix pyright errors in agents_runner/ui/widgets/radio_control.py

## File
File: `agents_runner/ui/widgets/radio_control.py`
Lines: 435

## Category
`object-to-int`

## Errors
```
  Line 435: Argument of type "object" cannot be assigned to parameter "x" of type "ConvertibleToInt" in function "__new__"
  Line 435: Argument of type "object" cannot be assigned to parameter "x" of type "ConvertibleToInt" in function "__new__"
```

## Fix
Cast `object` values to `int` before passing to functions expecting int.
Use `int(value)` or add a type guard.
Lines affected: [435]

## Verification
```bash
uv run pyright agents_runner/ui/widgets/radio_control.py
```
