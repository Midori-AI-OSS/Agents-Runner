# Task 024: Organize Theme Implementations

## Status
Ready for implementation

## Priority
Medium

## Description
Reorganize the theme implementation code in graphics.py by extracting each agent's theme into separate files within a themes subfolder. This improves code maintainability, reduces the size of graphics.py, and makes theme implementations easier to find and modify.

## Background
The last commit (task-023) removed legacy orb/shard renderer code from graphics.py. The task file stated that theme files should be placed in a themes subfolder, but this organizational refactor was not completed. Currently, all theme paint methods remain in graphics.py:
- _paint_codex_background (line 1279) 
- _paint_claude_background (line 1213)
- _paint_gemini_background (line 654)
- _paint_copilot_background (line 1017)

Additionally, theme-specific helper functions, dataclasses, and animation code are scattered throughout the 1559-line graphics.py file.

## Objectives
1. Create organized theme directory structure
2. Extract each theme's implementation into its own module
3. Maintain exact visual and behavioral parity with current implementation
4. Reduce graphics.py size and improve maintainability
5. Establish pattern for future theme additions

## Target Structure
```
agents_runner/ui/themes/
  __init__.py
  codex/
    __init__.py
    background.py
  claude/
    __init__.py
    background.py
  gemini/
    __init__.py
    background.py
  copilot/
    __init__.py
    background.py
```

## Subtasks
1. **task-024-theme-structure-setup.md** - Create directory structure and base files
2. **task-025-extract-gemini-theme.md** - Extract Gemini theme (simplest, good starting point)
3. **task-026-extract-claude-theme.md** - Extract Claude tree animation theme
4. **task-027-extract-copilot-theme.md** - Extract Copilot code typing theme (most complex)
5. **task-028-extract-codex-theme.md** - Extract Codex gradient/blob theme
6. **task-029-graphics-cleanup.md** - Clean up graphics.py and finalize delegation
7. **task-030-theme-integration-testing.md** - Comprehensive testing of all themes

## Technical Approach
- Each theme module will contain:
  - Agent-specific paint method
  - Agent-specific helper functions
  - Agent-specific dataclasses (e.g., _ClaudeBranchTip, _CopilotPane)
  - Agent-specific constants (e.g., _CLAUDE_SEGMENT_LIFETIME_S)
  - All imports needed by that theme
- GlassRoot in graphics.py will:
  - Import all theme modules
  - Maintain state variables
  - Delegate to appropriate theme module based on agent_cli
  - Pass necessary state to theme functions

## State Management Pattern

Theme functions will follow this signature pattern:

```python
def paint_<agent>_background(
    widget: QWidget,
    painter: QPainter,
    # State parameters (passed from GlassRoot)
    state_var1: TypeHint,
    state_var2: TypeHint,
    # ... additional state as needed
) -> None:
    """Paint the <agent> theme background."""
    ...
```

**Guidelines:**
- GlassRoot owns all state variables (RNG, orbs, panes, timers, etc.)
- Theme functions receive state as parameters
- Use type hints throughout
- Keep functions focused (prefer smaller functions over monoliths)

**Import Pattern:**
```python
from agents_runner.ui.themes.gemini import background as gemini_bg
from agents_runner.ui.themes.claude import background as claude_bg
from agents_runner.ui.themes.copilot import background as copilot_bg
from agents_runner.ui.themes.codex import background as codex_bg
```

**Commit Strategy:**
- Create feature branch: `refactor/theme-organization`
- One commit per completed subtask
- Commit message format: `[REFACTOR] Task NNN: Brief description`
- Test after each commit before proceeding
- Run linter after each commit: `ruff check agents_runner/ui/`

## Code Locations
- Source: `agents_runner/ui/graphics.py` (1559 lines)
- Target: `agents_runner/ui/themes/*/background.py` (new modules)

## Testing Strategy
- Manual visual testing for each theme
- Verify animations work correctly
- Check performance (CPU, memory)
- Test window resize and minimize
- Verify theme switching if supported

## Success Metrics
- graphics.py reduced to < 800 lines
- All themes render identically to before refactor
- No performance regression
- All animations work smoothly
- Code passes linter checks
- Clean module boundaries with minimal coupling

## Dependencies
None (can start immediately)

## Estimated Effort
- Structure setup: 15 minutes
- Each theme extraction: 30-60 minutes (depending on complexity)
- Cleanup and delegation: 30 minutes
- Testing: 45 minutes
- Total: ~4-5 hours

## Notes
- Follow existing code style conventions
- Maintain type hints throughout
- Keep commits small and focused
- Test after each theme extraction
- Do not modify visual behavior
- Preserve all state management logic
