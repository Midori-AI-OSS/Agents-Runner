# Task: Fix pyright errors in agents_runner/ui/animations.py

## File
File: `agents_runner/ui/animations.py`
Lines: 153

## Category
`animations-filter`

## Errors
```
  Line 153: Argument of type "_ButtonAnimationFilter" cannot be assigned to parameter "filterObj" of type "QObject" in function "installEventFilter"
```

## Fix
`_ButtonAnimationFilter` needs QObject compatibility for `installEventFilter`.
Either make the class inherit `QObject`, or use `cast(QObject, self._filter)`.

## Verification
```bash
uv run pyright agents_runner/ui/animations.py
```
