# Task: Fix pyright errors in agents_runner/ui/main_window_tasks_interactive_docker.py

## File
File: `agents_runner/ui/main_window_tasks_interactive_docker.py`
Lines: 687

## Category
`object-to-terminaloption`

## Errors
```
  Line 687: Argument of type "object" cannot be assigned to parameter "option" of type "TerminalOption" in function "launch_in_terminal"
```

## Fix
Line 687: `launch_in_terminal(terminal_opt, ...)` where `terminal_opt` is typed `object` (line 83) but `launch_in_terminal` expects `TerminalOption`.
Use `cast(TerminalOption, terminal_opt)` with the corrected variable name.
Add imports:
- `from typing import cast`
- `from agents_runner.terminal_apps import TerminalOption` (add alongside existing import of `launch_in_terminal` on line 39)

## Verification
```bash
uv run pyright agents_runner/ui/main_window_tasks_interactive_docker.py
```
