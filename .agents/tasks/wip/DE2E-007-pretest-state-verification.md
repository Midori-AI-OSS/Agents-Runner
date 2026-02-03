# Task: Add Pre-Test Container State Verification

**ID:** DE2E-007  
**Priority:** Medium  
**Estimated Effort:** 20-30 minutes  
**Type:** Enhancement

## Objective
Add explicit verification at the start of each test to ensure no container state pollution from previous tests.

## Current Behavior
- Tests assume clean Docker state
- No verification that previous test containers are gone
- No check for conflicting resources
- Silent failures possible if environment is dirty

## Expected Behavior
- Each test verifies clean starting state
- Clear error messages if pollution detected
- Optional: auto-cleanup of unexpected containers
- Tests can run reliably even after failures

## Acceptance Criteria
- [ ] Add helper function `verify_clean_docker_state()` using `_run_docker` helper
- [ ] Use session-scoped fixture for initial cleanup (not autouse per-test)
- [ ] Check for no containers with test prefix
- [ ] Check for no test-related networks/volumes
- [ ] Provide clear error message if state is dirty
- [ ] Use fail-fast approach for parallel test safety (not auto-cleanup)
- [ ] Depends on: DE2E-002 (cleanup patterns) and DE2E-003 (naming patterns)

## Implementation Notes
1. Add verification helper using existing `_run_docker` helper:
   ```python
   def verify_clean_docker_state(cleanup: bool = True) -> None:
       """Verify no leftover test containers exist.
       
       Args:
           cleanup: If True, remove found containers. If False, raise error.
       """
       # List containers with test prefix using _run_docker
       result = _run_docker(
           ["ps", "-a", "--filter", "name=agents-runner-test-",
            "--format", "{{.ID}}"],
           timeout_s=10.0
       )
       container_ids = [c for c in result.stdout.strip().split("\n") if c]
       
       if container_ids:
           if cleanup:
               for cid in container_ids:
                   try:
                       _run_docker(["rm", "-f", cid], timeout_s=5.0)
                   except Exception:
                       pass  # Best-effort
           else:
               raise RuntimeError(
                   f"Found {len(container_ids)} leftover containers: {container_ids}"
               )
   ```

2. Use session-scoped fixture (coordinates with DE2E-002):
   ```python
   @pytest.fixture(scope="session", autouse=True)
   def verify_docker_clean():
       verify_clean_docker_state(cleanup=True)
       yield
   ```

3. Note: Naming pattern `agents-runner-test-` depends on DE2E-003 implementation

4. For parallel test safety: use fail-fast (cleanup=False) to avoid race conditions

## Files to Modify
- `agents_runner/tests/test_docker_e2e.py`

## Testing
1. Manually create a test container: `docker run -d --name agents-runner-test-orphan alpine sleep 1000`
2. Run tests and verify it's detected and cleaned
3. Remove manual test: `docker rm -f agents-runner-test-orphan`

## References
- Docker CLI filtering: https://docs.docker.com/engine/reference/commandline/ps/#filter
