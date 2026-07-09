# Task: Fix pyright errors in agents_runner/ui/pages/settings_form.py

## File
File: `agents_runner/ui/pages/settings_form.py`
Lines: 446, 1007, 1020, 1028, 1037, 1065, 1077, 1205

## Category
`mixin-cast-qwidget`

## Errors
```
  Line 446: Argument of type "Self@SettingsFormMixin" cannot be assigned to parameter "parent" of type "QWidget | None" in function "create_add_button"
  Line 1007: Argument of type "Self@SettingsFormMixin" cannot be assigned to parameter "parent" of type "QWidget | None" in function "__init__"
  Line 1020: Argument of type "Self@SettingsFormMixin" cannot be assigned to parameter "parent" of type "QWidget | None" in function "warning"
  Line 1028: Argument of type "Self@SettingsFormMixin" cannot be assigned to parameter "parent" of type "QWidget | None" in function "__init__"
  Line 1037: Argument of type "Self@SettingsFormMixin" cannot be assigned to parameter "parent" of type "QWidget | None" in function "warning"
  Line 1065: Argument of type "Self@SettingsFormMixin" cannot be assigned to parameter "parent" of type "QWidget | None" in function "warning"
  Line 1077: Argument of type "Self@SettingsFormMixin" cannot be assigned to parameter "parent" of type "QWidget | None" in function "warning"
  Line 1205: Argument of type "Self@SettingsFormMixin" cannot be assigned to parameter "parent" of type "QWidget | None" in function "__init__"
```

## Fix
Wrap `self` with `cast(QWidget, self)` when passing to functions expecting QWidget.
Import: add `from typing import cast` if not present.
Lines affected: [446, 1007, 1020, 1028, 1037, 1065, 1077, 1205]

## Verification
```bash
uv run pyright agents_runner/ui/pages/settings_form.py
```
