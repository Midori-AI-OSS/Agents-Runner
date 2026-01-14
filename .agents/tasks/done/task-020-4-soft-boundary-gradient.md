# Task 020-4: Implement soft boundary gradient renderer

## Parent Task
task-020-background-codex-cloud-bands

## Description
Create rendering logic for a feathered, "airy" gradient at the boundary between top and bottom bands.

## Specific Actions
- Create method `_paint_band_boundary(painter, rect, split_ratio, top_color, bottom_color)`:
  - Calculate boundary y-position based on split_ratio (0.3 = 30% from top, 0.6 = 60% from top)
  - Create QLinearGradient perpendicular to boundary
  - Add multiple color stops for soft feathering:
    - Extend gradient ~50-100px above and below boundary line
    - Use smooth falloff (not just two-stop gradient)
  - Apply gradient to appropriate region
- Consider using QLinearGradient with multiple stops for best "airy" effect
- Test with different split_ratio values to ensure boundary moves smoothly

## Code Location
`agents_runner/ui/graphics.py` - Add method to `GlassRoot` class

## Technical Context
- Need to import: `from PySide6.QtGui import QLinearGradient` (not currently imported)
- Gradient extent: use 80px above and below boundary (middle of 50-100px range)
- Recommended stops: 7 stops for smooth blend (0.0, 0.15, 0.35, 0.5, 0.65, 0.85, 1.0)
- QLinearGradient pattern: create, set stops, use as brush with `painter.fillRect()`
- Boundary y-position formula: `boundary_y = rect.height() * split_ratio`

## Implementation Notes
- Create method: `_paint_band_boundary(painter, rect, split_ratio, top_color, bottom_color)`
- Calculate boundary line: `boundary_y = int(rect.height() * split_ratio)`
- Create gradient region: `boundary_y - 80` to `boundary_y + 80`
- Use QLinearGradient from (x, boundary_y - 80) to (x, boundary_y + 80)
- Add color stops at 0.0, 0.15, 0.35, 0.5, 0.65, 0.85, 1.0 with interpolated colors
- Consider caching gradient if colors don't change per frame

## Dependencies
- Task 020-3 (color blending utilities) - needs color values

## Acceptance Criteria
- Boundary is visibly soft and "airy" (not a crisp line)
- Boundary position correctly reflects split_ratio
- Gradient extends exactly 80px above and below boundary
- Uses 7 color stops for smooth falloff
- No visible banding or artifacts in gradient
- Import added: QLinearGradient
