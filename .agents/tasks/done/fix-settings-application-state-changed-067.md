# Task: Fix pyright errors in agents_runner/ui/pages/settings.py

## File
File: `agents_runner/ui/pages/settings.py`
Lines: 140

## Category
`application-state-changed`

## Errors
```
  Line 140: Cannot access attribute "applicationStateChanged" for class "QCoreApplication"
```

## Fix
Use QGuiApplication instead of QCoreApplication for applicationStateChanged.
`QCoreApplication.applicationStateChanged` -> `QGuiApplication.applicationStateChanged`
Import: `from PySide6.QtGui import QGuiApplication`

## Verification
```bash
uv run pyright agents_runner/ui/pages/settings.py
```
