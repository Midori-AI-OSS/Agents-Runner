# Task: Fix pyright errors in agents_runner/ui/pages/settings_form.py

## File
File: `agents_runner/ui/pages/settings_form.py`
Lines: 1834, 1864

## Category
`settings-form-autosave`

## Errors
```
  Line 1834: Cannot access attribute "_queue_debounced_autosave" for class "SettingsFormMixin*"
  Line 1864: Cannot access attribute "_queue_debounced_autosave" for class "SettingsFormMixin*"
```

## Fix
Mixin accessing `_queue_debounced_autosave` attribute. Add class-level type annotation or use cast.

## Verification
```bash
uv run pyright agents_runner/ui/pages/settings_form.py
```
