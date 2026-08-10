# 0100: GitHub Settings Spacer Removal

## Status
- Created: 2026-08-10

## Summary
In `agents_runner/ui/pages/settings_form.py`, grid row 8 of the GitHub Config pane contains a permanently-visible blank `QLabel("")` as a spacer in the left column. This prevents the row from collapsing when the rate-warning label is hidden. Remove the blank spacer and place the warning label to span the full row width so the row collapses when hidden and appears in the same location when shown.

## Scope
- **File:** `agents_runner/ui/pages/settings_form.py` only
- **No application behavior changes** (no settings, no config keys, no runtime logic)
- **No imports added or removed**

## Acceptance Criteria
1. The blank `QLabel("")` spacer at grid row 8 is removed.
2. The `self._github_poll_rate_warning_label` widget is placed directly in the grid spanning the full row (all 3 columns).
3. When the warning is hidden (`setVisible(False)`), row 8 collapses (no visible space consumed).
4. When the warning is shown (`setVisible(True)`), the label appears at the same visual location as before.
5. `ruff check` and `ruff format` pass on the modified file.
6. No other grid rows or widgets are changed.

## Implementation Notes
- Target: lines 769–774 in `_build_pages`, the `add_grid_row` call at row 8.
- Replace the `add_grid_row` call with a direct `github_grid.addWidget(self._github_poll_rate_warning_label, 8, 0, 1, 3)`.
- The `add_grid_row` helper always places a label at column 0; bypassing it is the correct fix here since we intentionally want zero-width at column 0 when hidden.
- `QLabel("")` is used nowhere else in this context — safe to remove from the `add_grid_row` call along with the call itself.

## Verification Checklist
- [ ] `ruff check` clean on `settings_form.py`
- [ ] `ruff format` clean on `settings_form.py`
- [ ] Grid row 8 no longer contains a blank `QLabel("")`
- [ ] Warning label `addWidget` spans columns 0–2 (colspan=3)
- [ ] `_github_poll_rate_warning_label` visibility toggling unchanged
- [ ] `_refresh_github_poll_rate_warning` method unchanged
