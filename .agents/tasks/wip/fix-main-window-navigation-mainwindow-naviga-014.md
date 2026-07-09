# Task: Fix pyright errors in agents_runner/ui/main_window_navigation.py

## File
File: `agents_runner/ui/main_window_navigation.py`
Lines: 22, 23, 24

## Category
`mainwindow-navigation`

## Errors
```
  Line 22: Cannot access attribute "minimumWidth" for class "MainWindowNavigationMixin*"
  Line 23: Cannot access attribute "minimumHeight" for class "MainWindowNavigationMixin*"
  Line 24: Cannot access attribute "resize" for class "MainWindowNavigationMixin*"
```

## Fix
Mixin accessing QWidget attributes on self.
Use `cast(QWidget, self)` when accessing `.width()`, `.minimumWidth()`, `.resize()`.

## Verification
```bash
uv run pyright agents_runner/ui/main_window_navigation.py
```
