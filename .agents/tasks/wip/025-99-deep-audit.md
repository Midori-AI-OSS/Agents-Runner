# Deep audit: Task 025 unified run planning

**Parent Task:** 025-unify-runplan-pydantic.md

## Scope
Comprehensive audit of completed task 025 implementation.

## Audit Areas

### Code Quality
- [ ] All Pydantic models follow best practices
- [ ] Type hints are complete and accurate
- [ ] Docstrings explain complex logic
- [ ] No code duplication between interactive/non-interactive paths
- [ ] Error handling is robust (image pull failures, container crashes, timeouts)

### Architecture
- [ ] Qt/UI isolation maintained (no Qt imports outside `agents_runner/ui/`)
- [ ] Planner is pure (no subprocess/filesystem in `plan_run`)
- [ ] Docker adapter interface is testable
- [ ] Boundaries are explicit between planning, execution, and UI

### Functionality
- [ ] Interactive runs get correct prompt guardrail prefix
- [ ] Non-interactive runs execute correctly
- [ ] Image pull happens before terminal/execution
- [ ] Container cleanup is reliable (stop and remove)
- [ ] Artifact collection works for both run types
- [ ] Desktop mode works correctly
- [ ] Timeout handling works as expected

### Testing
- [ ] Unit tests cover planner logic
- [ ] Tests use fake adapter (no Docker required)
- [ ] Tests are deterministic and fast
- [ ] Edge cases are tested (timeouts, failures, missing artifacts)

### Integration
- [ ] Works with existing environment system
- [ ] Compatible with all agent systems
- [ ] No regressions in existing functionality

## Actions
1. Review all files changed for task 025
2. Run full test suite: `uv run pytest`
3. Run linters: `uv run --group lint ruff check .`
4. Manual testing: run both interactive and non-interactive with different agents
5. Document any issues found in this file
6. If issues found: move task back to wip with notes
7. If all checks pass: delete this audit task

## Completion
Report findings and either approve (delete) or return to wip with detailed notes.
