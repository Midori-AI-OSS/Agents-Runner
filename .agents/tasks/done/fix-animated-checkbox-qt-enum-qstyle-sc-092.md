# Task: Fix pyright errors in agents_runner/ui/widgets/animated_checkbox.py

## File
File: `agents_runner/ui/widgets/animated_checkbox.py`
Lines: 50

## Category
`qt-enum-QStyle_SC`

## Errors
```
  Line 50: Cannot access attribute "SC_CheckBoxIndicator" for class "QStyle"
```

## Fix
`SC_CheckBoxIndicator` is not in `QStyle.SubControl` in Qt6 -- QCheckBox was de-complexified.
The correct API in Qt6 is `subElementRect()` with `QStyle.SubElement.SE_CheckBoxIndicator`.

Changes needed:
1. Replace `self.style().SC_CheckBoxIndicator` with `QStyle.SubElement.SE_CheckBoxIndicator` as the first arg to `subElementRect`
2. The call on line 47-51 must switch from `subControlRect(cc, opt, sc, widget)` to `subElementRect(subElement, widget)` -- see companion fix 091 for the full structural change
3. Add `from PySide6.QtWidgets import QStyle` to imports

This file (092), along with related files 091 and 093, all touch the same `subControlRect`/`styleOption`/`SC_CheckBoxIndicator` call and must be applied together.

## Verification
```bash
uv run pyright agents_runner/ui/widgets/animated_checkbox.py
```
