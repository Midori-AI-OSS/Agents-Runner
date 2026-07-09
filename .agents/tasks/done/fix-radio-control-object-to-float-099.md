# Task: Fix pyright errors in agents_runner/ui/widgets/radio_control.py

## File
File: `agents_runner/ui/widgets/radio_control.py`
Lines: 309, 348

## Category
`object-to-float`

## Errors
```
  Line 309: Argument of type "object" cannot be assigned to parameter "x" of type "ConvertibleToFloat" in function "__new__"
  Line 348: Argument of type "object" cannot be assigned to parameter "x" of type "ConvertibleToFloat" in function "__new__"
```

## Fix
Cast `object` values to `float` before passing to functions expecting float.
Use `float(value)` or add a type guard.
Lines affected: [309, 348]

## Verification
```bash
uv run pyright agents_runner/ui/widgets/radio_control.py
```
