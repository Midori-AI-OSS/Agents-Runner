# Task: Fix pyright errors in agents_runner/ui/widgets/animated_checkbox.py

## File
File: `agents_runner/ui/widgets/animated_checkbox.py`
Lines: 48

## Category
`qt-enum-QStyle_CC`

## Errors
```
  Line 48: Cannot access attribute "CC_CheckBox" for class "QStyle"
```

## Fix
Qt6 de-complexified QCheckBox -- `CC_CheckBox` no longer exists in `QStyle.ControlElement`.
The code on line 47-51 uses `subControlRect()` with `CC_CheckBox` and `SC_CheckBoxIndicator`,
but in Qt6 the correct API is `subElementRect()` with `QStyle.SubElement.SE_CheckBoxIndicator`.

Changes needed across lines 47-51:
1. Replace `subControlRect` with `subElementRect`
2. Replace `CC_CheckBox` with `QStyle.SubElement.SE_CheckBoxIndicator` (no longer a separate arg -- becomes the first arg to `subElementRect`)
3. Remove the `self.style().styleOption(self)` middle argument -- `subElementRect` takes only `(subElement, widget)`
4. Replace `SC_CheckBoxIndicator` with `self` (the widget parameter, already the last arg)
5. Add `from PySide6.QtWidgets import QStyle` to imports (currently only `QCheckBox` and `QWidget` are imported from `QtWidgets`)

This file (091), along with related files 092 and 093, all touch the same `subControlRect`/`styleOption`/`SC_CheckBoxIndicator` call and must be applied together.

## Verification
```bash
uv run pyright agents_runner/ui/widgets/animated_checkbox.py
```
