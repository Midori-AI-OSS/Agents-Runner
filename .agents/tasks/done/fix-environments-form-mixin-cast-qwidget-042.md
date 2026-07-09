# Task: Fix pyright errors in agents_runner/ui/pages/environments_form.py

## File
File: `agents_runner/ui/pages/environments_form.py`
Lines: 641

## Category
`mixin-cast-qwidget`

## Errors
```
  Line 641: Argument of type "Self@EnvironmentsFormMixin" cannot be assigned to parameter "parent" of type "QWidget | None" in function "getExistingDirectory"
```

## Fix
Wrap `self` with `cast(QWidget, self)` when passing to functions expecting QWidget.
Import: add `from typing import cast` if not present.
Lines affected: [641]

## Verification
```bash
uv run pyright agents_runner/ui/pages/environments_form.py
```
