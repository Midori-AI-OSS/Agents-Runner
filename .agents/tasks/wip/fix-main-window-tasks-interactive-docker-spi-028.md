# Task: Fix pyright errors in agents_runner/ui/main_window_tasks_interactive_docker.py

## File
File: `agents_runner/ui/main_window_tasks_interactive_docker.py`
Lines: 459, 482, 663, 1125

## Category
`spinner-color-str-to-qcolor`

## Errors
```
  Line 459: Argument of type "str | None" cannot be assigned to parameter "spinner_color" of type "QColor | None" in function "upsert_task"
  Line 482: Argument of type "str | None" cannot be assigned to parameter "spinner_color" of type "QColor | None" in function "upsert_task"
  Line 663: Argument of type "str | None" cannot be assigned to parameter "spinner_color" of type "QColor | None" in function "upsert_task"
  Line 1125: Argument of type "str | None" cannot be assigned to parameter "spinner_color" of type "QColor | None" in function "upsert_task"
```

## Fix
`spinner` is typed `str | None` (line 101) but `upsert_task` expects `QColor | None` for `spinner_color`.
Convert with `QColor(spinner) if spinner else None` at each call site.
Add import: `from PySide6.QtGui import QColor`.
Lines affected: [459, 482, 663, 1125]

## Verification
```bash
uv run pyright agents_runner/ui/main_window_tasks_interactive_docker.py
```
