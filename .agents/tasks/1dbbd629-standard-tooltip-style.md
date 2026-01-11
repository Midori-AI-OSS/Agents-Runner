# Task: Use standard tooltip for auto merge control

## Objective
Ensure the auto merge pull request checkbox uses the standard application tooltip system, matching the style and behavior of other tooltips in the application.

## Context
After removing the custom tooltip icon, the checkbox should use the built-in QCheckBox tooltip functionality that matches the rest of the application. The current tooltip text on the checkbox (lines 216-219) should be reviewed to ensure it follows application standards.

## Files to Modify
- `agents_runner/ui/pages/environments.py`

## Implementation Steps

1. Review the existing tooltip on `self._merge_agent_auto_start_enabled` (lines 216-219)
2. Verify it uses standard `setToolTip()` method (already correct - see code below)
3. Ensure tooltip text is concise and matches application conventions
4. Test that the tooltip appears on hover with standard timing
5. Verify no custom tooltip implementation exists (should be native Qt)
6. Verify tooltip styling matches other tooltips in the application

## Current Tooltip Implementation (Lines 216-219)

```python
self._merge_agent_auto_start_enabled.setToolTip(
    "When enabled, after a pull request creation task finishes, the program waits about 30 seconds\n"
    "and then starts a merge-agent task that resolves merge conflicts (if any) and merges the pull request."
)
```

This is already using the standard Qt `setToolTip()` method, which is correct.

## Comparison with Other Tooltips

The GitHub context checkbox (lines 204-209) is a good reference for tooltip style:
```python
self._gh_context_enabled.setToolTip(
    "When enabled, repository context (URL, branch, commit) is provided to the agent.\n"
    "For GitHub-managed environments: Always available.\n"
    "For folder-managed environments: Only if folder is a git repository.\n\n"
    "Note: This does NOT provide GitHub authentication - that is separate."
)
```

Both use:
- Standard `setToolTip()` method
- Multi-line text with `\n` separators
- Clear, descriptive language
- No custom styling or rendering

## Expected Behavior

Qt's standard tooltip system provides:
- Native tooltip appearance matching OS theme
- Standard timing (appears after ~500ms hover)
- Standard positioning (follows cursor or anchors to widget)
- No custom rendering or styling needed

## Current Tooltip Text
```
When enabled, after a pull request creation task finishes, the program waits about 30 seconds
and then starts a merge-agent task that resolves merge conflicts (if any) and merges the pull request.
```

## Acceptance Criteria
- [ ] Tooltip appears when hovering over the checkbox label
- [ ] Tooltip uses standard Qt tooltip styling (no custom rendering)
- [ ] Tooltip timing matches other tooltips in the application
- [ ] Tooltip text is clear and concise
- [ ] No separate tooltip icon is present
- [ ] Tooltip background and border match application theme

## Testing
1. Open a git-locked environment with auto merge enabled
2. Hover over the "Auto merge pull request" checkbox label
3. Verify tooltip appears with standard styling (native Qt appearance)
4. Compare tooltip appearance with other tooltips (e.g., "Provide GitHub context to agent")
   - Both should use same visual style
   - Both should have similar timing
   - Both should have similar positioning behavior
5. Verify tooltip disappears with standard timing when mouse moves away

## Important Note

**This task is primarily VERIFICATION, not implementation.**

The existing code already uses Qt's standard tooltip system correctly. No code changes may be necessary unless testing reveals unexpected behavior. The main goal is to confirm that:
- The tooltip icon widget (being removed in task d135f1de) is not interfering with standard tooltips
- After icon removal, the checkbox tooltip works as expected
- The tooltip matches the style of other application tooltips

If verification passes, this task can be marked complete with no code changes.
