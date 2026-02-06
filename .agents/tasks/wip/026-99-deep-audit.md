# Deep audit: Task 026 agent system plugins

**Parent Task:** 026-agent-system-plugins.md

## Scope
Comprehensive audit of completed task 026 implementation.

## Audit Areas

### Code Quality
- [ ] All Pydantic models follow best practices
- [ ] Plugin contract is clear and well-documented
- [ ] Type hints are complete and accurate
- [ ] No code duplication across plugins
- [ ] Error handling for plugin loading failures

### Architecture
- [ ] No Qt imports in plugin system (UI isolation maintained)
- [ ] Plugin discovery is safe (import failures don't crash app)
- [ ] Registry validates unique names and capabilities
- [ ] Plugin interface is extensible (easy to add new agents)
- [ ] Clear separation between plugin logic and UI theme resources

### Functionality
- [ ] All built-in plugins work correctly (codex, claude, copilot, gemini)
- [ ] Copilot correctly disables interactive support
- [ ] Plugin capabilities are respected by planner
- [ ] Prompt delivery modes work correctly (positional, flag, stdin)
- [ ] Config mounts are applied correctly per plugin
- [ ] UI themes load correctly per plugin

### Testing
- [ ] Plugin loading can be tested without actual agent CLIs
- [ ] Registry tests cover discovery and validation
- [ ] Edge cases tested (missing plugins, invalid configs)

### Integration
- [ ] Works with task 025 unified planner
- [ ] Works with existing environment system
- [ ] UI correctly queries plugin for theme
- [ ] No hardcoded agent system logic remains

### Migration Completeness
- [ ] All string-based branching removed
- [ ] No duplicate command-building logic
- [ ] Legacy code paths deleted (not commented out)
- [ ] Docstrings updated to reflect plugin system

## Actions
1. Review all files changed for task 026
2. Run full test suite: `uv run pytest`
3. Run linters: `uv run --group lint ruff check .`
4. Manual testing: run each agent system (codex, claude, copilot, gemini)
5. Verify UI themes display correctly for each agent
6. Search for any remaining hardcoded agent logic: `grep -r "codex\|claude\|copilot\|gemini" --include="*.py" | grep -v "agents_runner/agent_systems"`
7. Document any issues found in this file
8. If issues found: move task back to wip with notes
9. If all checks pass: delete this audit task

## Completion
Report findings and either approve (delete) or return to wip with detailed notes.
