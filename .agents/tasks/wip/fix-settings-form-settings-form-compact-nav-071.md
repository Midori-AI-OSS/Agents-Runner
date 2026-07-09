# Task: Fix pyright errors in agents_runner/ui/pages/settings_form.py

## File
File: `agents_runner/ui/pages/settings_form.py`
Lines: 851

## Category
`settings-form-compact-nav`

## Errors
```
  Line 851: Cannot access attribute "_compact_nav" for class "SettingsFormMixin*"
```

## Fix
Mixin accessing `_compact_nav` attribute. Add class-level type annotation or use cast.

## Verification
```bash
uv run pyright agents_runner/ui/pages/settings_form.py
```
