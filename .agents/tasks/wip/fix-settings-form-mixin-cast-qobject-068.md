# Task: Fix pyright errors in agents_runner/ui/pages/settings_form.py

## File
File: `agents_runner/ui/pages/settings_form.py`
Lines: 338, 342, 434

## Category
`mixin-cast-qobject`

## Errors
```
  Line 338: Argument of type "Self@SettingsFormMixin" cannot be assigned to parameter "filterObj" of type "QObject" in function "installEventFilter"
  Line 342: Argument of type "Self@SettingsFormMixin" cannot be assigned to parameter "parent" of type "QObject | None" in function "__init__"
  Line 434: Argument of type "Self@SettingsFormMixin" cannot be assigned to parameter "parent" of type "QObject | None" in function "__init__"
```

## Fix
Wrap `self` with `cast(QObject, self)` when passing to functions expecting QObject (lines 338, 342, 434).
`QObject` is already imported at line 9 of `settings_form.py` — only add `from typing import cast`.

## Verification
```bash
uv run pyright agents_runner/ui/pages/settings_form.py
```
