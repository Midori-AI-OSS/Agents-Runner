# Task: Fix pyright errors in agents_runner/ui/pages/environments_form.py

## File
File: `agents_runner/ui/pages/environments_form.py`
Lines: 576

## Category
`env-form-nav-clicked`

## Errors
```
  Line 576: Cannot access attribute "_on_nav_button_clicked" for class "EnvironmentsFormMixin*"
```

## Fix
Mixin accessing `_on_nav_button_clicked` attribute.
Add class-level type annotation: `_on_nav_button_clicked: Callable[..., Any]`.
Required imports: update `from typing import TYPE_CHECKING` to `from typing import TYPE_CHECKING, Any, Callable` (or add `from typing import Any, Callable` separately).

## Verification
```bash
uv run pyright agents_runner/ui/pages/environments_form.py
```
