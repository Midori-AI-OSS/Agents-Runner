# Task: Fix pyright errors in agents_runner/ui/pages/settings_form.py

## File
File: `agents_runner/ui/pages/settings_form.py`
Lines: 531, 826

## Category
`settings-form-pane-specs`

## Errors
```
  Line 531: Cannot access attribute "_pane_specs" for class "SettingsFormMixin*"
  Line 826: Cannot access attribute "_pane_specs" for class "SettingsFormMixin*"
```

## Fix
Mixin accessing `_pane_specs` attribute. Add class-level type annotation or use cast.

## Verification
```bash
uv run pyright agents_runner/ui/pages/settings_form.py
```
