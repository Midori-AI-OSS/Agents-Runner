# Task: Fix pyright errors in agents_runner/ui/pages/task_details.py

## File
File: `agents_runner/ui/pages/task_details.py`
Lines: 500

## Category
`qbytearray-to-bytes`

## Errors
```
  Line 500: Argument of type "QByteArray" cannot be assigned to parameter "o" of type "Iterable[SupportsIndex] | SupportsIndex | SupportsBytes | ReadableBuffer" in function "__new__"
  Line 500: Argument of type "QByteArray" cannot be assigned to parameter "o" of type "Iterable[SupportsIndex] | SupportsIndex | SupportsBytes | ReadableBuffer" in function "__new__"
```

## Fix
Call `.data()` on the QByteArray before passing to `bytes()`.
Change: `bytes(qbytearray_var)` -> `bytes(qbytearray_var.data())`
Lines affected: [500]

## Verification
```bash
uv run pyright agents_runner/ui/pages/task_details.py
```
