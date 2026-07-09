# Task: Fix pyright errors in agents_runner/ui/pages/github_work_coordinator.py

## File
File: `agents_runner/ui/pages/github_work_coordinator.py`
Lines: 705

## Category
`object-to-float`

## Errors
```
  Line 705: Argument of type "object | float" cannot be assigned to parameter "x" of type "ConvertibleToFloat" in function "__new__"
  Line 705: Argument of type "object | float" cannot be assigned to parameter "x" of type "ConvertibleToFloat" in function "__new__"
```

## Fix
Cast `object` values to `float` before passing to functions expecting float.
Use `float(value)` or add a type guard.
Lines affected: [705]

## Verification
```bash
uv run pyright agents_runner/ui/pages/github_work_coordinator.py
```
