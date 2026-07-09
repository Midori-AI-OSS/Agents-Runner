# Task: Fix pyright errors in agents_runner/ui/widgets/edge_fade_scroll_area.py

## File
File: `agents_runner/ui/widgets/edge_fade_scroll_area.py`
Lines: 124

## Category
`object-to-qobject`

## Errors
```
  Line 124: Argument of type "object" cannot be assigned to parameter "arg__1" of type "QObject" in function "eventFilter"
```

## Fix
Cast `object` to `QObject` before passing to `eventFilter`.
The variable name is `obj`, not `watched`.
Use `cast(QObject, obj)` from typing.
Required imports: add `from PySide6.QtCore import QObject` and `from typing import cast`.

## Verification
```bash
uv run pyright agents_runner/ui/widgets/edge_fade_scroll_area.py
```
