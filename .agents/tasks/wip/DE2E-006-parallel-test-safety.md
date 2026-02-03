# Task: Ensure Tests are Safe for Parallel Execution

**ID:** DE2E-006  
**Priority:** Medium  
**Estimated Effort:** 30-60 minutes  
**Type:** Enhancement

## Objective
Verify and document that docker e2e tests can run safely in parallel (pytest-xdist) without conflicts or race conditions.

## Current Behavior
- Tests likely run sequentially by default
- No explicit markers for parallel execution
- Unique task_ids and container names should prevent conflicts
- State directory isolation needs verification for parallel runs

## Expected Behavior
- Tests can run in parallel with `pytest -n auto`
- No resource conflicts (ports, container names, file paths)
- No race conditions in container lifecycle
- Tests complete successfully when run in parallel

## Acceptance Criteria
- [ ] Add pytest-xdist as optional dev dependency for validation
- [ ] Test parallel execution: `uv run pytest -n 3 agents_runner/tests/test_docker_e2e.py`
- [ ] Add pytest marks if tests must run sequentially
- [ ] Ensure port binding doesn't conflict (desktop/VNC ports)
- [ ] Note: Parallel execution is for validation only, not a production requirement

## Implementation Notes
1. Review port allocation in tests:
   - Desktop enabled tests use: `-p 127.0.0.1::6080` (random host port)
   - Should be safe for parallel execution

2. Check for shared temp directories:
   - Each test gets its own `tempfile.mkdtemp()`
   - Should be safe

3. Verify state file isolation:
   - Each fixture creates separate state.toml path
   - Should be safe

4. Test with pytest-xdist:
   ```bash
   uv pip install pytest-xdist
   uv run pytest -n 3 agents_runner/tests/test_docker_e2e.py -v
   ```

5. If issues found, consider:
   - Add `@pytest.mark.serial` for conflicting tests
   - Use unique port ranges per worker
   - Add file locking if needed

## Files to Modify
- `agents_runner/tests/test_docker_e2e.py` (add markers if needed)
- Note: pytest-xdist is optional dev dependency for validation, not required in pyproject.toml

## Testing
1. Install pytest-xdist: `uv add --dev pytest-xdist` (temporary for validation)
2. Run with 2 workers: `uv run pytest -n 2 agents_runner/tests/test_docker_e2e.py -v`
3. Run with 4 workers: `uv run pytest -n 4 agents_runner/tests/test_docker_e2e.py -v`
4. Check for timing issues, race conditions, or resource conflicts
5. Verify all tests pass consistently
6. Can remove pytest-xdist after validation if not needed

## References
- pytest-xdist: https://pytest-xdist.readthedocs.io/
- Pytest marks: https://docs.pytest.org/en/stable/mark.html
