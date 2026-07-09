# Task: Fix pyright errors in agents_runner/ui/main_window_auto_review.py

## File
File: `agents_runner/ui/main_window_auto_review.py`
Lines: 274

## Category
`mixin-cast-qwidget`

## Errors
```
  Line 274: Argument of type "Self@MainWindowAutoReviewMixin" cannot be assigned to parameter "parent" of type "QWidget | None" in function "__init__"
```

## Fix
Wrap `self` with `cast(QWidget, self)` when passing to functions expecting QWidget.
Import: add `from typing import cast` if not present.
Lines affected: [274]

## Verification
```bash
uv run pyright agents_runner/ui/main_window_auto_review.py
```
