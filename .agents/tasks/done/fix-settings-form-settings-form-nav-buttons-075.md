# Task: Fix pyright errors in agents_runner/ui/pages/settings_form.py

## File
File: `agents_runner/ui/pages/settings_form.py`
Lines: 850

## Category
`settings-form-nav-buttons`

## Errors
```
  Line 850: Cannot access attribute "_nav_buttons" for class "SettingsFormMixin*"
```

## Fix
Mixin accessing `_nav_buttons` attribute. Add class-level type annotation or use cast.

## Verification
```bash
uv run pyright agents_runner/ui/pages/settings_form.py
```
