# Task 026: Extract Claude Theme

## Parent Task
task-024-organize-theme-implementations (master)

## Description
Extract Claude theme implementation from graphics.py into a dedicated module at agents_runner/ui/themes/claude/background.py.

## Specific Actions
- Create `agents_runner/ui/themes/claude/background.py`
- Move Claude-specific code from graphics.py:
  - Dataclass: `_ClaudeBranchTip` (line 89)
  - Dataclass: `_ClaudeBranchSegment` (line 99)
  - Method: `_claude_palette()` (line 468)
  - Method: `_ensure_claude_tree()` (line 480)
  - Method: `_reset_claude_tree()` (line 488)
  - Method: `_tick_claude_tree()` (line 1124)
  - Method: `_paint_claude_background()` (line 1213)
  - Constants: `_CLAUDE_SEGMENT_LIFETIME_S = 90.0`, `_CLAUDE_SEGMENT_FADE_IN_S = 1.8` (lines 164-165)
- Add all necessary imports to background.py:
  - PySide6.QtCore: QPointF, Qt
  - PySide6.QtGui: QColor, QLinearGradient, QPainter, QPen, QRadialGradient
  - PySide6.QtWidgets: QWidget
  - Standard library: dataclass, math, random, time
- Convert methods to module-level functions accepting necessary state
- Update graphics.py to import and delegate to claude.background
- Ensure _claude_rng, _claude_tips, _claude_segments, and related state properly managed
- Move constants to module level:
  - `_CLAUDE_SEGMENT_LIFETIME_S = 90.0` (segments fade after 90 seconds)
  - `_CLAUDE_SEGMENT_FADE_IN_S = 1.8` (fade-in duration for new segments)

## Code Location
- New file: `agents_runner/ui/themes/claude/background.py`
- Source: `agents_runner/ui/graphics.py` (lines 89-106, 468-530, 1124-1277)

## Technical Context
- Claude theme uses animated branching tree pattern
- State management: RNG, branch tips list, segments list, timing
- Complex animation with branch growth, fading, and periodic resets
- Animation updates in _tick_claude_tree()
- Paint method draws segments with multi-layer pen effects

## Dependencies
- Task 024 (directory structure setup) must be complete
- Task 025 (Gemini extraction) should be complete for pattern consistency

## Acceptance Criteria
- All Claude-specific code moved to claude/background.py
- graphics.py delegates to new module correctly
- No functionality changes (visual output identical)
- Claude theme renders correctly when selected
- Tree animation continues to work smoothly
- Branch growth and fading behavior unchanged
- No import errors or missing dependencies
- Code runs without errors: `uv run main.py`
