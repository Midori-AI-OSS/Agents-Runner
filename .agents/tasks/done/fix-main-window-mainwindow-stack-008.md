# Task: Fix pyright errors in agents_runner/ui/main_window.py

## File
File: `agents_runner/ui/main_window.py`
Lines: 304

## Category
`mainwindow-stack`

## Errors
```
  Line 304: Cannot assign to attribute "_stack" for class "MainWindow*"
```

## Error
In `_mixin_hints.py` line 88, `_stack: QStackedWidget` (typed as QStackedWidget).
In `main_window.py` line 304, `self._stack = QWidget()` (assigned as QWidget).
So the type hint says QStackedWidget but the assignment creates a plain QWidget.

## Fix
Either:
(a) Change line 304 from `QWidget()` to `QStackedWidget()` (if the mixin type hint is correct). `QStackedWidget` is already imported at line 5 of `main_window.py`.
(b) Change the type hint in `_mixin_hints.py` from `QStackedWidget` to `QWidget`.

## Verification
```bash
uv run pyright agents_runner/ui/main_window.py
```
