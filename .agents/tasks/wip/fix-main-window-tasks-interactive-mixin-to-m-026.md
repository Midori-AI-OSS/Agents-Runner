# Task: Fix pyright errors in agents_runner/ui/main_window_tasks_interactive.py

## File
File: `agents_runner/ui/main_window_tasks_interactive.py`
Lines: 548, 678

## Category
`mixin-to-mainwindow`

## Errors
```
  Line 548: Argument of type "Self@MainWindowTasksInteractiveMixin" cannot be assigned to parameter "main_window" of type "MainWindow" in function "log_interactive_prep_diag"
  Line 678: Argument of type "Self@MainWindowTasksInteractiveMixin" cannot be assigned to parameter "main_window" of type "MainWindow" in function "launch_docker_terminal_task"
```

## Fix
Cast `self` to `MainWindow` when passing to functions expecting MainWindow.
Use `cast(MainWindow, self)` from typing.

## Verification
```bash
uv run pyright agents_runner/ui/main_window_tasks_interactive.py
```
