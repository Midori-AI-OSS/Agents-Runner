# Task: Fix pyright errors in agents_runner/ui/pages/settings_form.py

## File
File: `agents_runner/ui/pages/settings_form.py`
Lines: 1759, 1782

## Category
`settings-form-eventfilter`

## Errors
```
  Line 1759: Cannot access attribute "eventFilter" for class "object"
  Line 1782: Cannot access attribute "eventFilter" for class "object"
```

## Fix
`SettingsFormMixin` does not inherit from `QWidget`/`QObject`, so `super().eventFilter(...)` resolves to `object` which has no `eventFilter` method.
The lines already have `# pyright: ignore[reportUnknownVariableType]` comments; those suppress pyright successfully.
If the `# pyright: ignore` is removed or insufficient, use `QObject.eventFilter(self, watched, event)` instead of `super().eventFilter(watched, event)`.
`QObject` is already imported at line 9 of `settings_form.py`.

## Verification
```bash
uv run pyright agents_runner/ui/pages/settings_form.py
```
