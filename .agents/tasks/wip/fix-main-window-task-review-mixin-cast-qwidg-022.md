# Task: Fix pyright errors in agents_runner/ui/main_window_task_review.py

## File
File: `agents_runner/ui/main_window_task_review.py`
Lines: 34, 113, 132, 141, 148, 155

## Category
`mixin-cast-qwidget`

## Errors
```
  Line 34: Argument of type "Self@MainWindowTaskReviewMixin" cannot be assigned to parameter "parent" of type "QWidget | None" in function "information"
  Line 113: Argument of type "Self@MainWindowTaskReviewMixin" cannot be assigned to parameter "parent" of type "QWidget | None" in function "warning"
  Line 132: Argument of type "Self@MainWindowTaskReviewMixin" cannot be assigned to parameter "parent" of type "QWidget | None" in function "information"
  Line 141: Argument of type "Self@MainWindowTaskReviewMixin" cannot be assigned to parameter "parent" of type "QWidget | None" in function "information"
  Line 148: Argument of type "Self@MainWindowTaskReviewMixin" cannot be assigned to parameter "parent" of type "QWidget | None" in function "information"
  Line 155: Argument of type "Self@MainWindowTaskReviewMixin" cannot be assigned to parameter "parent" of type "QWidget | None" in function "question"
```

## Fix
Wrap `self` with `cast(QWidget, self)` when passing to functions expecting QWidget.
Import: add `from typing import cast` if not present.
Lines affected: [34, 113, 132, 141, 148, 155]

## Verification
```bash
uv run pyright agents_runner/ui/main_window_task_review.py
```
