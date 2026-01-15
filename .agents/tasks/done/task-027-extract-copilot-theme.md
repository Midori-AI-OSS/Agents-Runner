# Task 027: Extract Copilot Theme

## Parent Task
task-024-organize-theme-implementations (master)

## Description
Extract Copilot theme implementation from graphics.py into a dedicated module at agents_runner/ui/themes/copilot/background.py.

## Specific Actions
- Create `agents_runner/ui/themes/copilot/background.py`
- Move Copilot-specific code from graphics.py:
  - Dataclass: `_CopilotRenderedLine` (line 124)
  - Dataclass: `_CopilotActiveLine` (line 134)
  - Dataclass: `_CopilotPane` (line 153)
  - Method: `_copilot_font_metrics()` (line 700)
  - Method: `_ensure_copilot_sources()` (line 716)
  - Method: `_copilot_pick_snippet()` (line 734)
  - Method: `_ensure_copilot_panes()` (line 766)
  - Method: `_copilot_fill_pending()` (line 787)
  - Method: `_copilot_pick_color()` (line 797)
  - Method: `_copilot_pick_style()` (line 807)
  - Method: `_copilot_clamp_line()` (line 817)
  - Method: `_copilot_make_active_line()` (line 826)
  - Method: `_tick_copilot_typed_code()` (line 902)
  - Method: `_copilot_pane_rects()` (line 998)
  - Method: `_paint_copilot_background()` (line 1017)
- Add all necessary imports to background.py:
  - PySide6.QtCore: QPointF, QRectF, Qt
  - PySide6.QtGui: QColor, QFont, QFontDatabase, QFontMetricsF, QLinearGradient, QPainter, QPen, QRadialGradient, QStaticText
  - PySide6.QtWidgets: QWidget
  - Standard library: dataclass, pathlib.Path, random, time
- Convert methods to module-level functions accepting necessary state
- Update graphics.py to import and delegate to copilot.background
- Ensure all Copilot state properly managed: _copilot_rng, _copilot_panes, _copilot_source_files, font/metrics cache, etc.

## Code Location
- New file: `agents_runner/ui/themes/copilot/background.py`
- Source: `agents_runner/ui/graphics.py` (lines 124, 134, 153, 700-1122)

## Special Handling

**Static Method:** `_copilot_clamp_line()` (line 818) is currently a `@staticmethod`.
When moving to module, convert to regular module-level function (remove decorator, no `self` parameter).

**File System Access:** `_ensure_copilot_sources()` reads Python files from repository using
`Path(__file__).resolve().parents[2]` to find project root. Verify path resolution still works from new location.

## Technical Context
- Copilot theme uses animated code typing effect
- Most complex theme with multiple dataclasses and helper methods
- State management: RNG, panes, source files, font metrics cache
- Reads actual Python source files from repository
- Simulates typing with mistakes and backspacing
- Multiple panes with scrolling text effect

## Dependencies
- Task 024 (directory structure setup) must be complete
- Task 025 (Gemini extraction) and 026 (Claude extraction) should be complete for pattern consistency

## Acceptance Criteria
- All Copilot-specific code moved to copilot/background.py
- graphics.py delegates to new module correctly
- No functionality changes (visual output identical)
- Copilot theme renders correctly when selected
- Code typing animation works smoothly
- Mistake/backspace behavior unchanged
- Font rendering and pane layout unchanged
- Source file reading still works
- No import errors or missing dependencies
- Code runs without errors: `uv run main.py`
