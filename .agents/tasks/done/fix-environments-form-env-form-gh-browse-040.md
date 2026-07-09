# Task: Fix pyright errors in agents_runner/ui/pages/environments_form.py

## File
File: `agents_runner/ui/pages/environments_form.py`
Lines: 308

## Category
`env-form-gh-browse`

## Errors
```
  Line 308: Cannot assign to attribute "_gh_management_browse" for class "EnvironmentsFormMixin*"
```

## Fix
`_gh_management_browse` typed as QToolButton but assigned QPushButton.
Change type annotation to `QPushButton` or use appropriate type.

## Verification
```bash
uv run pyright agents_runner/ui/pages/environments_form.py
```
