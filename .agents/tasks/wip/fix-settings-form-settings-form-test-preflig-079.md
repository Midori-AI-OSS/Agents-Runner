# Task: Fix pyright errors in agents_runner/ui/pages/settings_form.py

## File
File: `agents_runner/ui/pages/settings_form.py`
Lines: 480

## Category
`settings-form-test-preflight`

## Errors
```
  Line 480: Cannot access attribute "_on_test_preflight" for class "SettingsFormMixin*"
```

## Fix
Mixin accessing `_on_test_preflight` attribute. Add class-level type annotation or use cast.

## Verification
```bash
uv run pyright agents_runner/ui/pages/settings_form.py
```
