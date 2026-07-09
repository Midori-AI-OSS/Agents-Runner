# Task: Fix pyright errors in agents_runner/ui/pages/settings_form.py

## File
File: `agents_runner/ui/pages/settings_form.py`
Lines: 848

## Category
`settings-form-nav-clicked`

## Errors
```
  Line 848: Cannot access attribute "_on_nav_button_clicked" for class "SettingsFormMixin*"
```

## Fix
Mixin accessing `_on_nav_button_clicked` attribute. Add class-level type annotation or use cast.

## Verification
```bash
uv run pyright agents_runner/ui/pages/settings_form.py
```
