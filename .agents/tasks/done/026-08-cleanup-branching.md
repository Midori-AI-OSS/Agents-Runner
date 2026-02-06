# Remove scattered agent system branching logic

**Parent Task:** 026-agent-system-plugins.md

## Scope
Clean up remaining hardcoded agent system logic now that plugin system is in use.

## Actions
1. Search codebase for remaining string comparisons on agent system names:
   ```bash
   grep -r "== ['\"]codex\|== ['\"]claude\|== ['\"]copilot\|== ['\"]gemini" --include="*.py" | grep -v "agents_runner/agent_systems"
   ```
2. Migrate each to use plugin queries (capabilities, mounts, command building)
3. Remove commented-out legacy branching code
4. Update docstrings that reference old hardcoded approach
5. Run linters and full test suite

## Acceptance
- No hardcoded agent system branching remains
- All agent systems work via plugin system
- Tests pass
- Passes linting
- One focused commit: `[CLEANUP] Remove scattered agent system branching logic`
Completion notes:

## Completion Notes

Successfully cleaned up scattered agent system branching logic:

1. **Plugin System Enhancement:**
   - Added `requires_github_token` capability to plugin model
   - Copilot plugin now declares GitHub token requirement via capability
   - New helper function `requires_github_token(agent_cli)` for checking

2. **Migrated Branching Logic:**
   - Docker worker helpers: GitHub token checks now use plugin capabilities
   - Container executor: Token forwarding uses plugin query
   - Preflight worker: Cross-agent token checks use plugin system
   - Interactive planner: GitHub token injection uses plugin capability

3. **Plugin Improvements:**
   - Claude plugin now handles `.claude.json` mount automatically
   - Removed hardcoded Claude logic from `agent_cli.py` helpers

4. **Code Quality:**
   - Replaced nested ternary with lookup dict in settings
   - Updated docstrings to reference plugin system
   - All linting passes

**Out of Scope:**
- UI command routing (legitimate UI-layer logic)
- Settings key mapping (configuration layer, not agent system logic)
- Theme name comparisons (UI theming, not agent system logic)
- Legacy helpers in agent_cli.py (used by old code paths for backward compatibility)

Commit: [CLEANUP] Remove scattered agent system branching logic
