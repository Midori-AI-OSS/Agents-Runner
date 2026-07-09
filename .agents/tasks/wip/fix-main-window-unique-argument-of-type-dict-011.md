# Task: Fix pyright errors in agents_runner/ui/main_window.py

## File
File: `agents_runner/ui/main_window.py`
Lines: 280

## Category
`dict-invariance-environments`

## Errors
```
  Line 280: Argument of type "dict[str, Environment]" cannot be assigned to parameter "environments"
            of type "dict[str, object]" in function "set_environments"
            Type parameter "_VT@dict" is invariant, but "Environment" is not the same as "object"
            Consider switching from "dict" to "Mapping" which is covariant in the value type
```

## Fix
Change the parameter type of `set_environments` from `dict[str, object]` to `dict[str, Environment]`, OR use `Mapping[str, object]` (from `collections.abc`) for the parameter type since `Mapping` is covariant.

Option A (preferred if `set_environments` is in our codebase):
```python
from collections.abc import Mapping

def set_environments(self, environments: Mapping[str, object]) -> None:
```

Option B:
```python
def set_environments(self, environments: dict[str, Environment]) -> None:
```

## Verification
```bash
uv run pyright agents_runner/ui/main_window.py
```
