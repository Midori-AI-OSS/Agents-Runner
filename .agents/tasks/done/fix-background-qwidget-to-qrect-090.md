# Task: Fix pyright errors in agents_runner/ui/themes/copilot/background.py

## File
File: `agents_runner/ui/themes/copilot/background.py`
Lines: 325, 594, 601

## Category
`qwidget-to-qrect`

## Errors
```
  Line 325: Argument of type "QWidget" cannot be assigned to parameter "rect" of type "QRect" in function "copilot_pane_rects"
  Line 594: Argument of type "QWidget" cannot be assigned to parameter "rect" of type "QRect" in function "ensure_copilot_panes"
  Line 601: Argument of type "QWidget" cannot be assigned to parameter "rect" of type "QRect" in function "copilot_font_metrics"
```

## Fix
Pass the widget's geometry/rect instead of the widget itself.
Change: `func(widget)` -> `func(widget.geometry())` or `func(widget.rect())`
Lines affected: [325, 594, 601]

## Verification
```bash
uv run pyright agents_runner/ui/themes/copilot/background.py
```
