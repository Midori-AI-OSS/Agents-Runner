# Remove duplicate run planning codepaths

**Parent Task:** 025-unify-runplan-pydantic.md

## Scope
Clean up legacy per-mode "plan assembly" code now that callers are migrated.

## Actions
1. Identify duplicate run planning code from before migration:
   ```bash
   # Look for legacy planning patterns
   grep -r "plan_run\|docker.*start\|docker.*exec" --include="*.py" | grep -v "agents_runner/planner"
   ```
2. Remove dead code paths that are no longer called
3. Remove commented-out legacy code
4. Update any docstrings/comments that reference old flow
5. Run linters and full test suite

## Acceptance
- No duplicate planning logic remains
- All tests still pass
- No broken references to removed code
- Passes linting
- One focused commit: `[CLEANUP] Remove duplicate run planning codepaths`
