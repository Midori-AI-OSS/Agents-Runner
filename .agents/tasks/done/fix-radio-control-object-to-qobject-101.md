# Task: Fix pyright errors in agents_runner/ui/widgets/radio_control.py

## File
File: `agents_runner/ui/widgets/radio_control.py`
Lines: 382

## Category
`object-to-qobject`

## Errors
```
  Line 382: Argument of type "object" cannot be assigned to parameter "watched" of type "QObject" in function "eventFilter"
```

## Fix
Cast `watched` (typed `object`) to `QObject` before passing to `super().eventFilter(...)`.
Use `cast(QObject, watched)` on line 382.
Add imports:
- `from PySide6.QtCore import QObject`
- `from typing import cast`

## Verification
```bash
uv run pyright agents_runner/ui/widgets/radio_control.py
```
