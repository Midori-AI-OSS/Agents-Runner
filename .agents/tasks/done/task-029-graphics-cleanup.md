# Task 029: Graphics Module Cleanup

## Parent Task
task-024-organize-theme-implementations (master)

## Description
Clean up graphics.py after theme extraction, ensuring proper imports, delegation, and removal of extracted code. Verify the module is lean and focused on coordination.

## Specific Actions
- Remove all extracted theme code from graphics.py:
  - Theme-specific dataclasses (Gemini, Claude, Copilot)
  - Theme-specific paint methods (all four agents)
  - Theme-specific helper methods
  - Theme-specific animation tick methods
- Add imports for new theme modules:
  ```python
  from agents_runner.ui.themes.gemini import background as gemini_background
  from agents_runner.ui.themes.claude import background as claude_background
  from agents_runner.ui.themes.copilot import background as copilot_background
  from agents_runner.ui.themes.codex import background as codex_background
  ```
- Update paintEvent() to delegate to appropriate theme module:
  - Determine current theme from agent_cli
  - Call corresponding paint function from theme module
  - Pass necessary state/context to theme functions
- Update animation timer callback to delegate tick functions:
  - Call theme-specific tick functions from imported modules
  - Pass necessary state and dt_s parameter
- Verify GlassRoot class manages state properly:
  - Keep state variables in GlassRoot
  - Pass state to theme functions as parameters
  - Ensure proper initialization and cleanup
- Check line count: graphics.py should be significantly smaller (target < 800 lines)
- Run linter to catch any issues: `ruff check agents_runner/ui/graphics.py`

## Code Location
- Modified file: `agents_runner/ui/graphics.py`
- Imports from: `agents_runner/ui/themes/*/background.py`

## Technical Context
- GlassRoot should become primarily a coordinator
- Theme modules should be self-contained
- State management pattern: GlassRoot owns state, themes receive it
- Delegation pattern: GlassRoot.paintEvent() determines theme and calls appropriate module

## Dependencies
- Task 024-028 (all theme extractions) must be complete

## Verification Checklist

After cleanup, verify each item:
- [ ] No orphaned dataclasses in graphics.py
- [ ] No orphaned helper methods in graphics.py (check with `grep "def _" agents_runner/ui/graphics.py`)
- [ ] No unused imports remaining
- [ ] All constants moved to appropriate themes
- [ ] GlassRoot class line count reduced to ~400-600 lines
- [ ] No duplicate code between graphics.py and theme modules
- [ ] All theme state variables still initialized in `__init__`
- [ ] paintEvent() delegation logic is clean and maintainable
- [ ] Animation timer delegation is correct

**Run these checks:**
```bash
# Check for orphaned theme code
grep -i "gemini\|claude\|copilot" agents_runner/ui/graphics.py | grep "def _"

# Verify line count (should be significantly reduced)
wc -l agents_runner/ui/graphics.py  # Target: <800 lines

# Check compilation
python -m py_compile agents_runner/ui/graphics.py

# Run linter
ruff check agents_runner/ui/graphics.py

# Test each theme
uv run main.py --agent codex
uv run main.py --agent claude
uv run main.py --agent gemini
uv run main.py --agent copilot
```

## Acceptance Criteria
- graphics.py successfully cleaned up
- All extracted code removed from graphics.py
- Proper imports added for all theme modules
- paintEvent() correctly delegates to theme modules
- Animation tick correctly delegates to theme modules
- All themes render correctly when selected
- No duplicate code between graphics.py and theme modules
- graphics.py line count reduced significantly (< 800 lines target)
- All verification checklist items pass
- Linter passes with no errors: `ruff check agents_runner/ui/graphics.py`
- Code runs without errors: `uv run main.py`
