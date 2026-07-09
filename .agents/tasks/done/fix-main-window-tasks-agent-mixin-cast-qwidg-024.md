# Task: Fix pyright errors in agents_runner/ui/main_window_tasks_agent.py

## File
File: `agents_runner/ui/main_window_tasks_agent.py`
Lines: 109, 116, 148, 243, 275, 290, 296, 371, 377, 411

## Category
`mixin-cast-qwidget`

## Errors
```
  Line 109: Argument of type "Self@MainWindowTasksAgentMixin" cannot be assigned to parameter "parent" of type "QWidget | None" in function "critical"
  Line 116: Argument of type "Self@MainWindowTasksAgentMixin" cannot be assigned to parameter "parent" of type "QWidget | None" in function "warning"
  Line 148: Argument of type "Self@MainWindowTasksAgentMixin" cannot be assigned to parameter "parent" of type "QWidget | None" in function "warning"
  Line 243: Argument of type "Self@MainWindowTasksAgentMixin" cannot be assigned to parameter "parent" of type "QWidget | None" in function "__init__"
  Line 275: Argument of type "Self@MainWindowTasksAgentMixin" cannot be assigned to parameter "parent" of type "QWidget | None" in function "warning"
  Line 290: Argument of type "Self@MainWindowTasksAgentMixin" cannot be assigned to parameter "parent" of type "QWidget | None" in function "warning"
  Line 296: Argument of type "Self@MainWindowTasksAgentMixin" cannot be assigned to parameter "parent" of type "QWidget | None" in function "warning"
  Line 371: Argument of type "Self@MainWindowTasksAgentMixin" cannot be assigned to parameter "parent" of type "QWidget | None" in function "warning"
  Line 377: Argument of type "Self@MainWindowTasksAgentMixin" cannot be assigned to parameter "parent" of type "QWidget | None" in function "warning"
  Line 411: Argument of type "Self@MainWindowTasksAgentMixin" cannot be assigned to parameter "parent" of type "QWidget" in function "resolve_launch_port_decision"
```

## Fix
Wrap `self` with `cast(QWidget, self)` when passing to functions expecting QWidget.
Import: add `from typing import cast` if not present.
Lines affected: [109, 116, 148, 243, 275, 290, 296, 371, 377, 411]

## Verification
```bash
uv run pyright agents_runner/ui/main_window_tasks_agent.py
```
