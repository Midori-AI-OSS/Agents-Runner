# Task: Fix pyright errors in agents_runner/ui/pages/settings_form.py

## File
File: `agents_runner/ui/pages/settings_form.py`
Lines: 1116, 1117

## Category
`settings-form-page-stack`

## Errors
```
  Line 1116: Cannot access attribute "_page_stack" for class "SettingsFormMixin*"
  Line 1117: Cannot access attribute "_pane_index_by_key" for class "SettingsFormMixin*"
```

## Fix
Mixin accessing `_page_stack / _pane_index_by_key` attribute. Add class-level type annotation or use cast.

## Verification
```bash
uv run pyright agents_runner/ui/pages/settings_form.py
```
