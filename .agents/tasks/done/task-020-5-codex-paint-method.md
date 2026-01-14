# Task 020-5: Create Codex-specific paint method

## Parent Task
task-020-background-codex-cloud-bands

## Description
Implement the main painting method that renders the two-band background composition for Codex.

## Specific Actions
- Create method `_paint_codex_background(self, painter: QPainter, rect: QRect)`:
  - Get current phase values (split_ratio, color phases)
  - Calculate top_color using `_get_top_band_color()`
  - Calculate bottom_color using `_get_bottom_band_color()`
  - Paint top band:
    - Fill from top to boundary position with top_color
  - Paint bottom band:
    - Fill from boundary position to bottom with bottom_color
  - Apply soft boundary blend using `_paint_band_boundary()`
  - Ensure proper layer composition (bands + boundary)
- Test that all components work together
- Verify painting performance is acceptable

## Code Location
`agents_runner/ui/graphics.py` - Add method to `GlassRoot` class

## Technical Context
- Current paint flow: `paintEvent()` → `_paint_theme()` → `_paint_orbs()` + shards (line 394-410)
- QPainter and QRect already available in paint context
- Performance target: < 5ms execution time on modern hardware
- Avoid per-frame allocations in hot path (reuse objects when possible)

## Implementation Notes
- Create method: `_paint_codex_background(self, painter: QPainter, rect: QRect)`
- Get phase values by calling `_calc_split_ratio()`, `_calc_top_phase()`, `_calc_bottom_phase()`
- Get colors by calling `_get_top_band_color()`, `_get_bottom_band_color()`
- Paint sequence:
  1. Calculate boundary_y: `int(rect.height() * split_ratio)`
  2. Fill top band: `painter.fillRect(0, 0, rect.width(), boundary_y, top_color)`
  3. Fill bottom band: `painter.fillRect(0, boundary_y, rect.width(), rect.height() - boundary_y, bottom_color)`
  4. Call `_paint_band_boundary()` over the boundary region
- Use `painter.save()` / `painter.restore()` if needed
- Profile with QElapsedTimer to verify < 5ms

## Dependencies
- Task 020-2 (phase calculation)
- Task 020-3 (color blending)
- Task 020-4 (soft boundary)

## Acceptance Criteria
- Method successfully renders two-band composition
- Colors and boundary update according to phase values
- No visual glitches or artifacts
- Performance is smooth (no lag during repaints)
- Execution time < 5ms measured with profiler
