# Task: Fix pyright errors in agents_runner/ui/widgets/stained_glass_button.py

## File
File: `agents_runner/ui/widgets/stained_glass_button.py`
Lines: 248, 249

## Category
`stained-glass-qcolor-overload`

## Errors
```
  Line 248: No overloads for "__init__" match the provided arguments
            Argument types: (*Unknown, int) (reportCallIssue)
  Line 249: "__getitem__" method not defined on type "object" (reportIndexIssue)
```

## Fix
Fix QColor constructor call for unpacking RGBA values. The current code uses `QColor(*values)` with an int alpha as second arg, which PySide6's QColor doesn't accept. The issue is that QColor can't unpack a variable-length tuple the way Qt5 could.

Change:
```python
QColor(*values, alpha)
```
To:
```python
QColor.fromRgb(*values[:3], alpha)
```
Or equivalently:
```python
QColor(*values[:3], values[3]) if len(values) == 4 else QColor(*values)
```

This also fixes the line 249 `__getitem__` error because the variable type becomes properly known after the fix.

## Verification
```bash
uv run pyright agents_runner/ui/widgets/stained_glass_button.py
```
