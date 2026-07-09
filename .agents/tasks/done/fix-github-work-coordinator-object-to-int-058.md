# Task: Fix pyright errors in agents_runner/ui/pages/github_work_coordinator.py

## File
File: `agents_runner/ui/pages/github_work_coordinator.py`
Lines: 468, 706, 790, 1016, 1023

## Category
`object-to-int`

## Errors
```
  Line 468: Argument of type "object | Literal[0]" cannot be assigned to parameter "x" of type "ConvertibleToInt" in function "__new__"
  Line 468: Argument of type "object | Literal[0]" cannot be assigned to parameter "x" of type "ConvertibleToInt" in function "__new__"
  Line 706: Argument of type "object | Literal[0]" cannot be assigned to parameter "x" of type "ConvertibleToInt" in function "__new__"
  Line 706: Argument of type "object | Literal[0]" cannot be assigned to parameter "x" of type "ConvertibleToInt" in function "__new__"
  Line 790: Argument of type "object | Literal[0]" cannot be assigned to parameter "x" of type "ConvertibleToInt" in function "__new__"
  Line 790: Argument of type "object | Literal[0]" cannot be assigned to parameter "x" of type "ConvertibleToInt" in function "__new__"
  Line 1016: Argument of type "object" cannot be assigned to parameter "x" of type "ConvertibleToInt" in function "__new__"
  Line 1016: Argument of type "object" cannot be assigned to parameter "x" of type "ConvertibleToInt" in function "__new__"
  Line 1023: Argument of type "object" cannot be assigned to parameter "x" of type "ConvertibleToInt" in function "__new__"
  Line 1023: Argument of type "object" cannot be assigned to parameter "x" of type "ConvertibleToInt" in function "__new__"
```

## Fix
Cast `object` values to `int` before passing to functions expecting int.
Use `int(value)` or add a type guard.
Lines affected: [468, 706, 790, 1016, 1023]

## Verification
```bash
uv run pyright agents_runner/ui/pages/github_work_coordinator.py
```
