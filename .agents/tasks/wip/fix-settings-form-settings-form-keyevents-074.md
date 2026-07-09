# Task: Fix pyright errors in agents_runner/ui/pages/settings_form.py

## File
File: `agents_runner/ui/pages/settings_form.py`
Lines: 1785, 1789

## Category
`settings-form-keyevents`

## Errors
```
  Line 1785: Cannot access attribute "keyPressEvent" for class "object"
  Line 1789: Cannot access attribute "keyReleaseEvent" for class "object"
```

## Fix
`SettingsFormMixin` does not inherit from `QWidget`, so `super().keyPressEvent(event)` / `super().keyReleaseEvent(event)` resolves to `object` which has no such methods.
Replace `super()` with explicit `QWidget` call:
- `QWidget.keyPressEvent(self, event)` (line 1785)
- `QWidget.keyReleaseEvent(self, event)` (line 1789)
Or use `cast(QWidget, self).keyPressEvent(event)` / `cast(QWidget, self).keyReleaseEvent(event)`.
`QWidget` is already imported at line 31 of `settings_form.py`.

## Verification
```bash
uv run pyright agents_runner/ui/pages/settings_form.py
```
