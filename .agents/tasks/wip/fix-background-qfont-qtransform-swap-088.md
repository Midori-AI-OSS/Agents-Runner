# Task: Fix pyright errors in agents_runner/ui/themes/copilot/background.py

## File
File: `agents_runner/ui/themes/copilot/background.py`
Lines: 290, 368, 400

## Category
`qfont-qtransform-swap`

## Errors
```
  Line 290: Argument of type "QFont" cannot be assigned to parameter "matrix" of type "QTransform" in function "prepare"
  Line 368: Argument of type "QFont" cannot be assigned to parameter "matrix" of type "QTransform" in function "prepare"
  Line 400: Argument of type "QFont" cannot be assigned to parameter "matrix" of type "QTransform" in function "prepare"
```

## Fix
Swap arguments so QFont is passed to the `font` parameter, not `matrix`.
The error is on `QStaticText.prepare()`, not `QPainter.prepare()`.
Use keyword arguments: `static_text.prepare(font=font)` on each affected line.
Lines affected: [290, 368, 400]

## Verification
```bash
uv run pyright agents_runner/ui/themes/copilot/background.py
```
