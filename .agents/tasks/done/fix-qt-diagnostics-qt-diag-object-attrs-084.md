# Task: Fix pyright errors in agents_runner/ui/qt_diagnostics.py

## File
File: `agents_runner/ui/qt_diagnostics.py`
Lines: 59, 60, 61, 62

## Category
`qt-diag-object-attrs`

## Errors
```
  Line 59: Cannot access attribute "file" for class "object"
  Line 60: Cannot access attribute "file" for class "object"
  Line 60: Cannot access attribute "line" for class "object"
  Line 61: Cannot access attribute "function" for class "object"
  Line 62: Cannot access attribute "function" for class "object"
```

## Fix
Accessing `.file`, `.line`, `.function` on `object` type.
Add a Protocol/class or use `hasattr` checks with proper typing.

## Verification
```bash
uv run pyright agents_runner/ui/qt_diagnostics.py
```
