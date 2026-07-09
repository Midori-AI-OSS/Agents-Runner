# Task: Fix pyright errors in agents_runner/ui/desktop_viewer/app.py

## File
File: `agents_runner/ui/desktop_viewer/app.py`
Lines: 175

## Category
`setwindowicon-qcoreapp`

## Errors
```
  Line 175: Cannot access attribute "setWindowIcon" for class "QCoreApplication"
```

## Fix
`setWindowIcon` is on `QGuiApplication` (or QApplication), not `QCoreApplication`.
Cast app or import QGuiApplication.

## Verification
```bash
uv run pyright agents_runner/ui/desktop_viewer/app.py
```
