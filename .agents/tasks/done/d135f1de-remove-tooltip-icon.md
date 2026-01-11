# Task: Remove tooltip icon from auto merge control

## Objective
Remove the information icon (QToolButton) next to the "Auto merge pull request" checkbox. Users should not see any clickable or hover-only icon next to the checkbox.

## Context
The current implementation shows a `QToolButton` with an information icon (`SP_MessageBoxInformation`) that displays a tooltip when the auto merge feature is blocked. This icon should be completely removed.

## Files to Modify
- `agents_runner/ui/pages/environments.py`

## Implementation Steps

1. Locate the tooltip icon widget definition (around line 225-231):
   - `self._merge_agent_auto_start_info`
2. Remove the widget from the merge agent row layout (line 239)
3. Remove all references to `self._merge_agent_auto_start_info`:
   - Widget initialization (lines 225-231)
   - Layout addition (line 239)
   - Visibility updates (lines 270, 557, 644)
   - Tooltip updates (lines 558, 647)
4. Clean up any logic that sets visibility or tooltip for this widget

## Current Code to Remove

### Widget Initialization (Lines 225-231):
```python
self._merge_agent_auto_start_info = QToolButton(general_tab)
self._merge_agent_auto_start_info.setAutoRaise(True)
self._merge_agent_auto_start_info.setFocusPolicy(Qt.FocusPolicy.NoFocus)
self._merge_agent_auto_start_info.setIcon(
    self.style().standardIcon(QStyle.SP_MessageBoxInformation)
)
self._merge_agent_auto_start_info.setVisible(False)
```

### Layout Addition (Line 239):
```python
merge_agent_layout.addWidget(self._merge_agent_auto_start_info)
```

### Visibility Logic (Lines 644-647):
```python
self._merge_agent_auto_start_info.setVisible(
    bool(is_git_locked and not merge_supported and merge_blocked_reason)
)
self._merge_agent_auto_start_info.setToolTip(merge_blocked_reason)
```

### Cleanup Logic (Lines 557-558):
```python
self._merge_agent_auto_start_info.setVisible(False)
self._merge_agent_auto_start_info.setToolTip("")
```

## Layout Context

The icon is in the `merge_agent_layout` which is the layout for `self._merge_agent_row` (created at line 235):
```python
self._merge_agent_row = QWidget(general_tab)
merge_agent_layout = QHBoxLayout(self._merge_agent_row)
merge_agent_layout.setContentsMargins(0, 0, 0, 0)
merge_agent_layout.setSpacing(BUTTON_ROW_SPACING)
merge_agent_layout.addWidget(self._merge_agent_auto_start_enabled)  # Checkbox
merge_agent_layout.addWidget(self._merge_agent_auto_start_info)     # Icon to remove
merge_agent_layout.addStretch(1)
```

After removal, layout should only contain:
```python
merge_agent_layout.addWidget(self._merge_agent_auto_start_enabled)
merge_agent_layout.addStretch(1)
```

## Code Sections to Remove
- Widget initialization (lines 225-231)
- Layout addition (line 239)
- Visibility logic (lines 644-647)

## Acceptance Criteria
- [ ] No information icon appears next to the "Auto merge pull request" checkbox
- [ ] No QToolButton widget exists for merge agent tooltip
- [ ] The checkbox row layout only contains the checkbox itself
- [ ] No visual artifacts or spacing issues after removal
- [ ] Git-locked environments show clean checkbox without icon

## Additional Notes
- After removal, `QToolButton` import at line 21 may be unused (check if used elsewhere)
- The parent widget `general_tab` is defined earlier in the init method
- The `merge_blocked_reason` variable (lines 636-643) will no longer be used for icon tooltip
- Four locations need cleanup: initialization (225-231), layout (239), visibility logic (644-647), and reset logic (557-558)

## Testing
1. Open a git-locked environment
2. Verify the auto merge checkbox appears without any icon
3. Test with auto merge disabled (no GitHub context)
4. Verify no icon appears when the feature is blocked
5. Verify tooltip still works on the checkbox label itself
