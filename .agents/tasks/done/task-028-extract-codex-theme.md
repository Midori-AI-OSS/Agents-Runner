# Task 028: Extract Codex Theme

## Parent Task
task-024-organize-theme-implementations (master)

## Description
Extract Codex theme implementation from graphics.py into a dedicated module at agents_runner/ui/themes/codex/background.py.

## Specific Actions
- Create `agents_runner/ui/themes/codex/background.py`
- Move Codex-specific code from graphics.py:
  - Method: `_blend_colors()` (line 297)
  - Method: `_get_top_band_color()` (line 325)
  - Method: `_get_bottom_band_color()` (line 344)
  - Method: `_calc_split_ratio()` (line 363) - calculates gradient split position
  - Method: `_calc_top_phase()` (line 375) - calculates top band color phase
  - Method: `_calc_bottom_phase()` (line 387) - calculates bottom band color phase
  - Method: `_update_background_animation()` (line 399) - updates animation timer
  - Method: `_paint_codex_background()` (line 1279)
  - Method: `_paint_band_boundary_diagonal()` (line 1330)
  - Method: `_paint_codex_blobs()` (line 1387)
  - Method: `_paint_band_boundary()` (line 1462)
  - Constant: `_CODEX_BOUNDARY_ANGLE_DEG = 15.0` (line 162)
- Add all necessary imports to background.py:
  - PySide6.QtCore: QPointF, QRectF
  - PySide6.QtGui: QColor, QLinearGradient, QPainter, QRadialGradient
  - PySide6.QtWidgets: QWidget
  - Standard library: math, random
- Convert methods to module-level functions accepting necessary state
- Update graphics.py to import and delegate to codex.background
- Ensure Codex state properly managed: phase values, blob state, animation timer, etc.
- Move constant to module level: `_CODEX_BOUNDARY_ANGLE_DEG = 15.0` (diagonal boundary angle)

## Code Location
- New file: `agents_runner/ui/themes/codex/background.py`
- Source: `agents_runner/ui/graphics.py` (lines 162, 297-399, 1279-1559)

## Technical Context
- Codex theme uses two-band gradient with diagonal boundary
- Color blending between top (DarkBlue/DarkGreen) and bottom bands
- Soft color blobs overlay for organic appearance
- Phase-based animation for color cycling (uses calc methods)
- Most visually complex gradient system

**Phase Calculation System:**
- `_calc_split_ratio()` determines position of diagonal boundary
- `_calc_top_phase()` and `_calc_bottom_phase()` calculate color cycle phases
- `_update_background_animation()` manages animation timing
- These methods are Codex-specific and should be extracted with theme

**Boundary Rendering:**
- `_paint_band_boundary_diagonal()` and `_paint_band_boundary()` may overlap in functionality
- Verify during extraction which is actually used by Codex theme

## Dependencies
- Task 024 (directory structure setup) must be complete
- Task 025-027 (other theme extractions) should be complete for pattern consistency

## Acceptance Criteria
- All Codex-specific code moved to codex/background.py
- graphics.py delegates to new module correctly
- No functionality changes (visual output identical)
- Codex theme renders correctly when selected
- Two-band gradient and diagonal boundary render correctly
- Color blob overlay works as before
- Phase-based animation continues smoothly
- No import errors or missing dependencies
- Code runs without errors: `uv run main.py`
