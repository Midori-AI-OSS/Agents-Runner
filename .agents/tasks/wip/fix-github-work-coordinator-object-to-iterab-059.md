# Task: Fix pyright errors in agents_runner/ui/pages/github_work_coordinator.py

## File
File: `agents_runner/ui/pages/github_work_coordinator.py`
Lines: 559

## Category
`object-to-iterable`

## Errors
```
  Line 559: Argument of type "object" cannot be assigned to parameter "global_usernames" of type "Iterable[object]" in function "effective_trusted_users"
```

## Fix
Cast `object` to the expected iterable type.
Add a type guard or use `cast(list[str], value)`.
Required import: add `from typing import cast` (not currently imported).
Lines affected: [559]

## Verification
```bash
uv run pyright agents_runner/ui/pages/github_work_coordinator.py
```
