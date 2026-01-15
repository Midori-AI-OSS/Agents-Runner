# Task 025: Extract Gemini Theme

## Parent Task
task-024-organize-theme-implementations (master)

## Description
Extract Gemini theme implementation from graphics.py into a dedicated module at agents_runner/ui/themes/gemini/background.py.

## Specific Actions
- Create `agents_runner/ui/themes/gemini/background.py`
- Move Gemini-specific code from graphics.py:
  - Dataclass: `_GeminiChromaOrb` (line 110)
  - Method: `_gemini_palette()` (line 531)
  - Method: `_ensure_gemini_orbs()` (line 539)
  - Method: `_constrain_gemini_orbs()` (line 610)
  - Method: `_tick_gemini_chroma_orbs()` (line 620)
  - Method: `_paint_gemini_background()` (line 654)
- Add all necessary imports to background.py:
  - PySide6.QtCore: QPointF
  - PySide6.QtGui: QColor, QLinearGradient, QPainter, QRadialGradient
  - PySide6.QtWidgets: QWidget
  - Standard library: dataclass, math, random
- Convert methods to module-level functions accepting necessary state
- Update graphics.py to import and delegate to gemini.background
- Ensure _gemini_rng, _gemini_orbs state is properly managed

## Code Location
- New file: `agents_runner/ui/themes/gemini/background.py`
- Source: `agents_runner/ui/graphics.py` (lines 110, 531-698)

## Technical Context
- Gemini theme uses animated color orbs with Google brand colors
- State management: Random number generator and orb list
- Animation updates happen in _tick_gemini_chroma_orbs()
- Paint method called from GlassRoot.paintEvent()
- Orbs move with velocity and acceleration
- `_constrain_gemini_orbs()` prevents orbs from leaving viewport boundaries

## Dependencies
- Task 024 (directory structure setup) must be complete

## Acceptance Criteria
- All Gemini-specific code moved to gemini/background.py
- graphics.py delegates to new module correctly
- No functionality changes (visual output identical)
- Gemini theme renders correctly when selected
- Animation continues to work smoothly
- No import errors or missing dependencies
- Code runs without errors: `uv run main.py`
