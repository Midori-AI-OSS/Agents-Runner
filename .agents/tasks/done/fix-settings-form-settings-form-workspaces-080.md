# Task: Fix pyright errors in agents_runner/ui/pages/settings_form.py

## File
File: `agents_runner/ui/pages/settings_form.py`
Lines: 1754

## Category
`settings-form-workspaces`

## Errors
```
  Line 1754: Cannot access attribute "move_task_workspaces_requested" for class "SettingsFormMixin*"
```

## Fix
Mixin accessing `move_task_workspaces_requested` attribute. Add class-level type annotation or use cast.

## Verification
```bash
uv run pyright agents_runner/ui/pages/settings_form.py
```
