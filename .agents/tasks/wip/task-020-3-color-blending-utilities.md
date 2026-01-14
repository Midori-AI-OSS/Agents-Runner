# Task 020-3: Implement color blending utilities

## Parent Task
task-020-background-codex-cloud-bands

## Description
Create utility functions to smoothly blend between specified colors.

## Specific Actions
- Create function `_blend_colors(color1, color2, t)` where t is 0.0 to 1.0
  - Accept QColor or hex strings as input
  - Return QColor
  - Implement linear RGB interpolation (or consider perceptual blending if needed)
- Create function `_get_top_band_color(phase)`:
  - Blend between #ADD8E6 (LightBlue) and #FF8C00 (DarkOrange)
  - Use phase value (0.0 to 1.0) from phase calculation
- Create function `_get_bottom_band_color(phase)`:
  - Choose two appropriate dark grays (e.g., #3A3A3A and #2A2A2A)
  - Blend between them using phase value
  - Ensure grays preserve readability
- Test color output at various phase values

## Code Location
`agents_runner/ui/graphics.py` - Add helper methods to `GlassRoot` class

## Technical Context
- QColor already imported from `PySide6.QtGui` (line 16)
- Current themes use QColor throughout (see `_AgentTheme` dataclass, line 49)
- Linear RGB interpolation formula: `r = r1 + (r2 - r1) * t` (same for g, b)
- Suggested bottom grays: `#2A2A2A` (darker) and `#3A3A3A` (lighter)
- Consider caching QColor objects if created repeatedly (performance optimization)

## Implementation Notes
- Create methods: `_blend_colors(c1, c2, t)`, `_get_top_band_color(phase)`, `_get_bottom_band_color(phase)`
- Accept QColor or hex strings in `_blend_colors`, always return QColor
- Use linear interpolation in RGB space (simple and fast)
- Top band: phase 0.0 = #ADD8E6, phase 1.0 = #FF8C00
- Bottom band: phase 0.0 = #2A2A2A, phase 1.0 = #3A3A3A
- Test edge cases: phase 0.0, 0.5, 1.0

## Dependencies
None (can be developed in parallel with other tasks)

## Acceptance Criteria
- Color blending is smooth with no banding
- Top band colors match spec: LightBlue ↔ DarkOrange
- Bottom band uses two subtle dark grays (#2A2A2A, #3A3A3A)
- Colors are readable and don't cause visual strain
- Method signatures use type hints (QColor parameters and returns)
