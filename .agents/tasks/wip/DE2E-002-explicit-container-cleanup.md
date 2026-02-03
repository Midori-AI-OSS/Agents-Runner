# Task: Add Explicit Container Cleanup Between Tests

**ID:** DE2E-002  
**Priority:** High  
**Estimated Effort:** 30-45 minutes  
**Type:** Enhancement

## Objective
Implement explicit container cleanup in test fixtures to ensure containers are fully removed before the next test starts.

## Current Behavior
- Tests set `auto_remove=True` in config
- Container removal happens asynchronously via Docker daemon
- No explicit wait for removal completion
- Race condition: next test may start before container fully cleaned up

## Expected Behavior
- Each test fixture should explicitly verify container removal
- Add cleanup verification in fixture teardown
- Ensure container name is available for reuse (though UUID prevents conflicts)
- Clean up any orphaned containers from previous failed runs

## Acceptance Criteria
- [ ] Add fixture finalizer that checks for container removal
- [ ] Implement timeout-based wait for container to be removed
- [ ] Add cleanup of any containers with `agents-runner-` prefix at test session start
- [ ] Handle case where container is already removed (don't fail)
- [ ] Use best-effort cleanup (don't fail tests if cleanup fails)

## Implementation Notes
1. Add session-scoped fixture to cleanup all test containers before run:
   ```python
   @pytest.fixture(scope="session", autouse=True)
   def cleanup_test_containers():
       # Remove any leftover test containers before session
       # Use _run_docker helper: _run_docker(["ps", "-a", "--filter", "name=agents-runner-", "--format", "{{.ID}}"])
       # Handle errors gracefully - cleanup is best-effort
   ```

2. In `test_config` fixture, add finalizer:
   ```python
   def finalizer():
       if container_id:
           # Wait up to 10s for container to be removed
           for _ in range(10):
               try:
                   _inspect_state(container_id)
               except subprocess.CalledProcessError:
                   # Container removed successfully
                   break
               time.sleep(1)
   request.addfinalizer(finalizer)
   ```

3. Use existing `_run_docker` and `_inspect_state` helpers from `agents_runner.docker.process` (already imported)

4. Follow pattern from lines 297-301 in test file for error handling

## Files to Modify
- `agents_runner/tests/test_docker_e2e.py`

## Testing
1. Run single test multiple times in succession
2. Verify no "name already in use" errors
3. Check `docker ps -a` shows no leftover test containers

## References
- Pytest finalizers: https://docs.pytest.org/en/stable/fixture.html#adding-finalizers-directly
