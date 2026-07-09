# Task: Fix pyright errors in agents_runner/ui/main_window_persistence.py

## File
File: `agents_runner/ui/main_window_persistence.py`
Lines: 132, 169, 178

## Category
`mainwindow-persistence`

## Errors
```
  Line 132: Cannot access attribute "_REMOVED_IDE_SETTINGS_KEYS" for class "MainWindowPersistenceMixin*"
  Line 169: Cannot access attribute "_REMOVED_IDE_SETTINGS_KEYS" for class "MainWindowPersistenceMixin*"
  Line 178: Cannot access attribute "_REMOVED_LEGACY_SETTINGS_KEYS" for class "MainWindowPersistenceMixin*"
```

## Fix
Mixin class attributes `_REMOVED_IDE_SETTINGS_KEYS` / `_REMOVED_LEGACY_SETTINGS_KEYS`
missing type annotations. Add class-level type annotations.

## Verification
```bash
uv run pyright agents_runner/ui/main_window_persistence.py
```
