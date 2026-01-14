# Task 019-03: Update interactive launch behavior with desktop defaults

## Parent
task-019-new-task-interactive-desktop-mounted.md

## Problem
When desktop is enabled, the primary click on "Run Interactive" should launch WITH desktop by default, and the dropdown should provide a "Without desktop" override option.

## Prerequisites
- Task 019-02 must be completed (desktop enablement data flowing to NewTaskPage)

## Desktop Script Source
The desktop preflight script should be loaded from prompts using existing pattern:
```python
desktop_script = load_prompt(
    os.path.join(self._host_codex_dir, "prompts/interactive_desktop_preflight.prompt"),
    "Interactive desktop preflight",
)
```
Reference the existing `_on_launch_with_desktop()` method for the pattern.

## Signal Management
DO NOT use try/except around disconnect. Instead:
1. Add instance variable to track current slot: `_current_interactive_slot: Callable | None = None`
2. Create helper method `_reconnect_interactive_button(new_slot)` for safe reconnection
3. Use helper method in `_sync_interactive_options()` to update button behavior

```python
def _reconnect_interactive_button(self, new_slot) -> None:
    """Safely reconnect the interactive button click handler."""
    if hasattr(self, '_current_interactive_slot') and self._current_interactive_slot:
        try:
            self._run_interactive.clicked.disconnect(self._current_interactive_slot)
        except (RuntimeError, TypeError):
            pass  # Already disconnected
    self._run_interactive.clicked.connect(new_slot)
    self._current_interactive_slot = new_slot
```

## Location
- `agents_runner/ui/pages/new_task.py`

## Changes Required
1. Add new QAction `_run_interactive_no_desktop` in `__init__()`:
   - Text: "Without desktop"
   - Connect to new method `_on_launch_without_desktop()`

2. Update `_sync_interactive_options()`:
   - When desktop is enabled (from `_env_desktop_enabled`):
     - Set menu to `_run_interactive_menu`
     - Update menu to contain only "Without desktop" action
     - Use helper method to wire primary button to `_on_launch_with_desktop`
   - When desktop is not enabled:
     - Set menu to None (no dropdown)
     - Use helper method to wire primary button to `_on_launch` (no desktop)

3. Add `_on_launch_without_desktop()` method:
   - Call `self._emit_interactive_launch(extra_preflight_script="")`

4. Use helper method to wire button behavior:
   - Call `self._reconnect_interactive_button(self._on_launch_with_desktop)` when desktop enabled
   - Call `self._reconnect_interactive_button(self._on_launch)` when desktop not enabled

## Acceptance Criteria
- [ ] When desktop enabled, primary click launches WITH desktop
- [ ] When desktop enabled, dropdown shows "Without desktop" option
- [ ] "Without desktop" option launches interactive without desktop script
- [ ] When desktop not enabled, no dropdown shown
- [ ] When desktop not enabled, primary click launches without desktop
- [ ] Signal connections updated correctly without duplicate handlers

## Implementation Notes
- Menu should contain "Without desktop" when desktop enabled (inverse of current "With desktop")
- Primary button behavior changes based on desktop enablement
- Use the `_reconnect_interactive_button()` helper method to safely manage signal connections
- Current menu item "With desktop" should be removed; replaced with "Without desktop"
- Import Callable from typing if not already imported for type hints
