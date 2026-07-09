# Task: Fix pyright errors in agents_runner/ui/pages/settings_form.py

## File
File: `agents_runner/ui/pages/settings_form.py`
Lines: 1757, 1817

## Category
`settings-form-isvisible`

## Errors
```
  Line 1757: Cannot access attribute "isVisible" for class "SettingsFormMixin*"
  Line 1817: Cannot access attribute "isVisible" for class "SettingsFormMixin*"
```

## Fix
Mixin accessing `isVisible (needs cast(QWidget, self))` attribute. Add class-level type annotation or use cast.

## Verification
```bash
uv run pyright agents_runner/ui/pages/settings_form.py
```
