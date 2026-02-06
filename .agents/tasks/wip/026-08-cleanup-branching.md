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
