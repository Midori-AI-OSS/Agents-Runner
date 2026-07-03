# Cleanup: Align new environment wizard with settings/env page patterns

## Summary
Fix navigation locking, animation, compact mode, section headers, header card, and other mismatches between the wizard and the reference settings/environments pages.

## Page Locking (CRITICAL)
- On initial open, **only page 1 (General Info) is accessible**. Nav buttons for pages 2-5 must be disabled (grayed out / `setEnabled(False)`).
- Once page 1 validation passes (name non-empty, folder exists OR clone URL is valid + clone test passed), unlock ALL remaining pages at once.
- The bottom Next button still advances sequentially; Back works normally.
- Clicking a nav button directly jumps to that page (once unlocked).

## Slide/Opacity Animation (CRITICAL)
- Add `_animate_stack(forward)` method matching `settings.py:262-306` / `environments_navigation.py:116-159`:
  - 210ms slide (16px) + opacity fade (0->1) via QParallelAnimationGroup
  - QPropertyAnimation on `pos` and `graphicsEffect` (opacity)
  - Cleanup on finish: reset pos, remove graphics effect
  - Store `_pane_animation` and `_pane_rest_pos` as instance attrs

## Compact Navigation Mode (CRITICAL)
- Add `_compact_nav` QComboBox with `objectName="SettingsCompactNav"` matching settings.py:97-101
- Add `_compact_mode` bool, `_update_navigation_mode()` called on resizeEvent
- Threshold: `LEFT_NAV_COMPACT_THRESHOLD` (1080) from constants.py
- When compact: hide left nav panel, show combo box. When wide: show nav, hide combo.
- Combo items: page titles, `currentIndexChanged` -> navigate to that page

## Section Headers in Left Nav (CRITICAL)
- Add `section` field to `_WizardPaneSpec` dataclass
- Group nav buttons under QLabel section headers (`objectName="SettingsNavSection"`)
- Suggested sections:
  - "Setup" -> General Info
  - "Runtime" -> Runtime & Agents, Desktop & Cache
  - "Automation" -> GitHub Behavior, AgentsNova Automation

## Header GlassCard (CRITICAL)
- Add a top-level GlassCard header above the main content card
- Title: "New Environment Wizard" (matching setWindowTitle)
- Styled with fontSize=18px, font-weight=750, same as Settings header

## Nav Button Dict (CRITICAL)
- Change `self._nav_buttons: list[QToolButton]` -> `self._nav_buttons: dict[str, QToolButton]` keyed by spec.key
- Add `self._pane_index_by_key: dict[str, int]` for key->stack index lookup
- Add `_register_page(key, widget)` method matching env/settings pattern
- Rename `self._stack` -> `self._page_stack`

## Method Name Alignment
- Rename `_create_pane_specs()` -> `_default_pane_specs()`

## Spacing Constant
- Replace literal `body_layout.setSpacing(10)` with `body_layout.setSpacing(GRID_VERTICAL_SPACING)`

## Body Stretch
- Remove stretch factor 1 from `content_layout.addWidget(body, 1)` -> `content_layout.addWidget(body)`

## create_stretch_row Consistency
- For checkboxes added via `add_grid_row` without `create_stretch_row`, wrap them with `create_stretch_row` to match environment form behavior (e.g., `_use_cross_agents`, `_headless_desktop_enabled`)

## Tint Alpha
- Change alpha from 22 to 13 to match environments.py:198

## Files to modify
- `agents_runner/ui/dialogs/new_environment_wizard.py` - all changes
- `agents_runner/ui/constants.py` - import `GRID_VERTICAL_SPACING`, `LEFT_NAV_BUTTON_SPACING`, `LEFT_NAV_COMPACT_THRESHOLD`

## Verification
- `uv run ruff format .`
- `uv run ruff check .`
- `uv run basedpyright`
- Import check: `uv run python -c "from agents_runner.ui.dialogs.new_environment_wizard import NewEnvironmentWizard"`

## Completion
- Implemented wizard navigation locking, keyed navigation registration, compact navigation, section headers, stack animation, header card, spacing/stretch alignment, checkbox stretch rows, and tint alpha alignment.
- Verification run: `uv run ruff format .`, `uv run ruff check .`, `uv run basedpyright`, `uv run basedpyright agents_runner/ui/dialogs/new_environment_wizard.py`, import check, and an offscreen wizard navigation lock/unlock check.
- `uv run basedpyright` still reports pre-existing project errors outside `agents_runner/ui/dialogs/new_environment_wizard.py`; the targeted wizard check passed with 0 errors.
