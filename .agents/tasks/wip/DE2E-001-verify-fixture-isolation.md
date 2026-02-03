# Task: Verify Test Fixture Isolation

**ID:** DE2E-001  
**Priority:** High  
**Estimated Effort:** 15-30 minutes  
**Type:** Investigation + Fix

## Objective
Ensure that each docker e2e test runs with completely isolated fixtures to prevent state leakage between tests.

## Current Behavior
- Tests use `test_config` fixture (function-scoped)
- Fixture creates temp directories but may not guarantee complete isolation
- Multiple tests may share fixture state inadvertently

## Expected Behavior
Each test should have:
- Unique task_id (already implemented via timestamp)
- Isolated temp_state_dir
- Separate workdir and codex_dir
- No shared state between test runs

## Acceptance Criteria
- [ ] Verify `test_config` fixture scope is `function` (not `module` or `session`)
- [ ] Confirm each test invocation creates new temp directories
- [ ] Add explicit assertion at test start to verify unique task_id

## Implementation Notes
1. Check pytest fixture decorators for scope
2. Consider adding `autouse=False` explicitly if needed
3. Verify no module-level state pollution
4. Note: This applies to existing test file only - no new tests per AGENTS.md policy

## Files to Modify
- `agents_runner/tests/test_docker_e2e.py` (existing tests only, per AGENTS.md line 78-83)

## Testing
Run tests with `-v` and `-s` flags to see fixture execution:
```bash
uv run pytest agents_runner/tests/test_docker_e2e.py -v -s
```

## References
- Pytest fixture scopes: https://docs.pytest.org/en/stable/fixture.html#scope-sharing-fixtures-across-classes-modules-packages-or-session
