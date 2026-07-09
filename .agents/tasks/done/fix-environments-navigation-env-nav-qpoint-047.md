# Task: Fix pyright errors in agents_runner/ui/pages/environments_navigation.py

## File
File: `agents_runner/ui/pages/environments_navigation.py`
Lines: 153

## Category
`env-nav-qpoint`

## Errors
```
  Line 153: Argument of type "Any | None" cannot be assigned to parameter "arg__1" of type "QPoint" in function "move"
```

## Fix
`Any | None` cannot be assigned to `QPoint`.
Check for None before calling move: `if pos is not None: widget.move(pos)`.

## Verification
```bash
uv run pyright agents_runner/ui/pages/environments_navigation.py
```
