# Integrate UI theme selection with plugin system

**Parent Task:** 026-agent-system-plugins.md

## Scope
Update UI background system to select theme by plugin name (remove hardcoded mapping).

## Actions
1. Locate UI background/theme selection code in `agents_runner/ui/` (check theme manager, background widgets, or main window styling code)
2. Refactor to query plugin for `ui_theme.theme_name`
3. Remove hardcoded agent-to-theme mapping logic
4. Add fallback to "midoriai" theme if plugin has no theme spec
5. Ensure theme resources still load correctly
6. Keep Qt isolated in `agents_runner/ui/`
7. Run linters and manual UI testing

**Implementation Pattern Example:**
```python
# Old approach (remove):
if agent == 'codex':
    theme = 'codex'
elif agent == 'claude':
    theme = 'claude'
# ...

# New approach (use):
plugin = registry.get_plugin(agent_name)
theme = plugin.ui_theme.theme_name if plugin.ui_theme else "midoriai"
```

## Acceptance
- UI queries plugin system for theme name
- No hardcoded per-agent theme mapping
- All agent systems still display correct backgrounds
- Fallback theme works
- Passes linting
- One focused commit: `[REFACTOR] Integrate UI theme selection with plugin system`

## Completion
**Status:** Complete  
**Commit:** af0431a - [REFACTOR] Integrate UI theme selection with plugin system

### Changes Made:
1. Refactored `_theme_for_agent()` in `agents_runner/ui/graphics.py` to query plugin registry instead of hardcoded if/else chain
2. Added plugin registry discovery in `agents_runner/ui/runtime/app.py` before UI initialization
3. Implemented fallback to "midoriai" theme when plugin has no `ui_theme` spec
4. All existing theme names (codex, claude, copilot, gemini, midoriai) work correctly
5. Tested unknown agent names correctly fallback to "midoriai"
6. All linters passed (ruff format + ruff check)
