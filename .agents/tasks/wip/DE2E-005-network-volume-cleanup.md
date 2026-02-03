# Task: Add Docker Network and Volume Cleanup

**ID:** DE2E-005  
**Priority:** Medium  
**Estimated Effort:** 30-45 minutes  
**Type:** Enhancement

## Objective
Implement cleanup of Docker networks and volumes that may be created during test execution to prevent resource leaks.

## Current Behavior
- Tests create containers with default networking
- No explicit network or volume creation in tests
- Docker may create anonymous volumes or networks
- No cleanup of these resources after tests

## Expected Behavior
- Identify any networks/volumes created during tests
- Clean them up in test teardown
- Add session-level cleanup for orphaned resources
- Document which resources are expected

## Acceptance Criteria
- [ ] Investigate which networks/volumes are actually created during tests (if any)
- [ ] Add session fixture to cleanup orphaned test networks (if needed)
- [ ] Add session fixture to cleanup orphaned test volumes (if needed)
- [ ] Ensure cleanup doesn't affect non-test containers
- [ ] Use best-effort cleanup (don't fail tests if cleanup fails)

## Implementation Notes
1. First, investigate which resources are actually created:
   ```bash
   docker network ls --filter "name=agents-runner"
   docker volume ls --filter "name=agents-runner"
   ```

2. If resources found, add cleanup fixtures using `_run_docker` helper:
   ```python
   @pytest.fixture(scope="session", autouse=True)
   def cleanup_docker_resources():
       yield
       # Cleanup networks (best-effort, ignore errors)
       try:
           result = _run_docker(
               ["network", "ls", "--filter", "name=agents-runner-", "--format", "{{.ID}}"],
               timeout_s=10.0
           )
           for network_id in result.stdout.strip().split("\n"):
               if network_id:
                   try:
                       _run_docker(["network", "rm", network_id], timeout_s=5.0)
                   except Exception:
                       pass  # Best-effort cleanup
       except Exception:
           pass
       
       # Similar for volumes
   ```

3. Note: Tests use default Docker networking (no explicit network creation in test file)

4. Label approach for filtering requires changes to docker worker code (outside test scope)

## Files to Modify
- `agents_runner/tests/test_docker_e2e.py` (if resources are actually created)

## Testing
1. Run full test suite
2. Check for leftover networks: `docker network ls`
3. Check for leftover volumes: `docker volume ls`  
4. Verify cleanup removes test resources only

## References
- Docker network cleanup: https://docs.docker.com/engine/reference/commandline/network_prune/
- Docker volume cleanup: https://docs.docker.com/engine/reference/commandline/volume_prune/
