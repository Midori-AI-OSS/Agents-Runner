# Task: Fix pyright errors in agents_runner/ui/pages/artifacts_utils.py

## File
File: `agents_runner/ui/pages/artifacts_utils.py`
Lines: 28

## Category
`artifacts-utils-float`

## Errors
```
  Line 28: Type "float" is not assignable to declared type "int"
```

## Fix
`float` value assigned to variable typed as `int`.
Use `int(...)` to cast, or change the type annotation to `float`.

## Verification
```bash
uv run pyright agents_runner/ui/pages/artifacts_utils.py
```
