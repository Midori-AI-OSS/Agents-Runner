# Task: Enhance Container Name Uniqueness for Tests

**ID:** DE2E-003  
**Priority:** Medium  
**Estimated Effort:** 20-30 minutes  
**Type:** Enhancement

## Objective
Add test-specific prefixes to container names to make them easily identifiable and ensure uniqueness even if UUID collision occurs.

## Current Behavior
- Container names use: `f"agents-runner-{uuid.uuid4().hex[:10]}"`
- Test containers are indistinguishable from production containers

## Expected Behavior
- Test containers should have distinct naming: `agents-runner-test-{test_name}-{uuid}`
- Easy to identify test containers for manual cleanup
- Even safer uniqueness guarantees

## Acceptance Criteria
- [ ] Modify test fixtures to override container naming
- [ ] Use test function name in container name
- [ ] Keep UUID for uniqueness
- [ ] Ensure name doesn't exceed Docker's 63-character limit
- [ ] Note: Depends on DE2E-002 for cleanup logic with new naming pattern

## Implementation Notes
1. Add `request` fixture parameter to `test_config`:
   ```python
   def test_config(temp_state_dir, request):
       test_name = request.node.name[:20]  # Truncate if needed
       task_id = f"test-{test_name}-{int(time.time() * 1000)}"
   ```

2. Note: Current test file already uses `task_id = f"test-task-{int(time.time() * 1000)}"` (line 82)

3. Container naming flows through: config → worker → container creation (verify actual path)

4. Alternative: Pass custom container name to DockerRunnerConfig if supported

5. Depends on: DE2E-002 cleanup implementation will use new naming pattern

## Files to Modify
- `agents_runner/tests/test_docker_e2e.py`
- Possibly: `agents_runner/docker/agent_worker_setup.py` (if adding override support)

## Testing
1. Run tests and verify container names include test function name
2. Check `docker ps` output shows clear test container identification
3. Verify name length stays under 63 chars
4. Verify actual container names with: `docker ps -a --format "{{.Names}}"`

## References
- Docker container naming rules: https://docs.docker.com/engine/reference/run/#name
- Pytest request fixture: https://docs.pytest.org/en/stable/reference.html#request
