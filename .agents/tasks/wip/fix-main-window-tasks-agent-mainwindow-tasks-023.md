# Task: Fix pyright errors in agents_runner/ui/main_window_tasks_agent.py

## File
File: `agents_runner/ui/main_window_tasks_agent.py`
Lines: 816, 817, 818

## Category
`mainwindow-tasks-agent-attrs`

## Errors
```
  Line 816: Cannot assign to attribute "_runner_config" for class "Task"
  Line 817: Cannot assign to attribute "_runner_prompt" for class "Task"
  Line 818: Cannot assign to attribute "_agent_selection" for class "Task"
```

## Fix
Assigning to `_runner_config`, `_runner_prompt`, `_agent_selection` on Task objects.
Add `# pyright: ignore[reportAttributeAccessIssue]` or add type stubs.
Lines affected: [816, 817, 818]

## Verification
```bash
uv run pyright agents_runner/ui/main_window_tasks_agent.py
```
