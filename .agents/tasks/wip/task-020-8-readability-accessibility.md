# Task 020-8: Test readability and accessibility

## Parent Task
task-020-background-codex-cloud-bands

## Description
Ensure the new background maintains good readability for text and UI elements.

## Specific Actions
- Test text readability on both bands:
  - Open application with various content types
  - Verify text is readable when background is LightBlue
  - Verify text is readable when background is DarkOrange
  - Verify text is readable on bottom dark gray bands
  - Check readability during color transitions
- Test UI element visibility:
  - Verify cards/panels are readable on both bands
  - Check button visibility and contrast
  - Verify any overlay elements remain visible
- Test at different window sizes:
  - Small window (minimum size)
  - Medium window (typical size)
  - Large window (maximized)
  - Verify boundary position doesn't cause readability issues at any size
- If readability issues found:
  - Adjust colors (darker/lighter as needed)
  - Adjust boundary blend width
  - Add subtle overlay to improve contrast if needed

## Code Location
Testing in running application, potential adjustments in `graphics.py`

## Technical Context
- WCAG AA contrast ratio minimum: 4.5:1 for normal text, 3:1 for large text
- Contrast testing: use browser DevTools color picker or online contrast checker
- Current UI: dark theme with light text (existing contrast should be maintained)
- Cards/panels likely have their own backgrounds (verify they remain visible)
- Top band at #FF8C00 (orange) may need contrast verification for light text

## Implementation Notes
- Launch app with `uv run main.py`, select Codex
- Test text readability matrix:
  - [ ] Light text on #ADD8E6 (light blue) - may need darker blue
  - [ ] Light text on #FF8C00 (orange) - verify sufficient contrast
  - [ ] Light text on #2A2A2A (dark gray) - should be excellent
  - [ ] Light text on #3A3A3A (lighter gray) - should be excellent
  - [ ] Text during color transitions (verify no "strobe" effect)
- Test UI elements:
  - [ ] Cards remain visible on both bands
  - [ ] Buttons have sufficient contrast
  - [ ] Border/outline elements visible
  - [ ] Focus indicators visible
- Window size testing:
  - [ ] Small window: verify boundary doesn't split important content
  - [ ] Medium window: verify typical use case readability
  - [ ] Large window: verify no contrast issues at any position
- If issues found:
  - Darken light blue to #A0C8E8 or similar for better contrast
  - Adjust orange to #FF9500 if needed
  - Document all color changes in commit message

## Dependencies
- Task 020-7 (visual validation complete)

## Acceptance Criteria
- All text remains readable on both bands
- UI elements (cards, buttons) remain clearly visible
- No accessibility concerns with color choices
- Readability is maintained at all window sizes
- Any necessary color adjustments are documented
- Contrast ratios meet WCAG AA (4.5:1 for normal text)
