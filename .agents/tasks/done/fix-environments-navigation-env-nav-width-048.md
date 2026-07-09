# Task: Fix pyright errors in agents_runner/ui/pages/environments_navigation.py

## File
File: `agents_runner/ui/pages/environments_navigation.py`
Lines: 172

## Category
`env-nav-width`

## Errors
```
  Line 172: Cannot access attribute "width" for class "EnvironmentsNavigationMixin*"
```

## Fix
Mixin accessing `width` attribute from QWidget.
Use `cast(QWidget, self).width()`.
Required imports: add `from typing import cast` and `from PySide6.QtWidgets import QWidget` (neither is currently imported).

## Verification
```bash
uv run pyright agents_runner/ui/pages/environments_navigation.py
```
