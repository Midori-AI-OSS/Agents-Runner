# Task: Implement Per-Test Image Layer Isolation

**ID:** DE2E-004  
**Priority:** Low  
**Estimated Effort:** 30-45 minutes  
**Type:** Enhancement

## Objective
Ensure tests don't rely on shared image state and consider using test-specific image tags or variants where needed.

## Current Behavior
- All tests use `TEST_IMAGE = "alpine:latest"`
- Image is pulled once and reused
- Tests share the same base image layers
- No verification of image state between tests

## Expected Behavior
- Tests should either:
  1. Use a pinned image digest for reproducibility, OR
  2. Use separate tagged images per test scenario if needed
- Document image requirements
- Add image cleanup in test teardown

## Acceptance Criteria
- [ ] Pin `TEST_IMAGE` to specific version (e.g., `alpine:3.19`) instead of `latest`
- [ ] Add session-scoped fixture to pull image once
- [ ] Leverage existing `ensure_test_image()` function (lines 109-115)
- [ ] Add test to verify image hasn't been modified during test run

## Implementation Notes
1. Change TEST_IMAGE constant (line 42):
   ```python
   TEST_IMAGE = "alpine:3.19.1"  # Pinned for reproducibility
   ```

2. Convert existing `ensure_test_image()` (lines 109-115) to session-scoped fixture:
   ```python
   @pytest.fixture(scope="session", autouse=True)
   def ensure_test_image_available():
       """Ensure test image is available before any tests run."""
       ensure_test_image()
       yield TEST_IMAGE
       # Note: Do not cleanup image - expensive to re-pull, keep cached
   ```

3. Remove individual `ensure_test_image()` calls from each test (they become redundant)

4. Note: Current implementation already uses `_run_docker` helper for image operations

## Files to Modify
- `agents_runner/tests/test_docker_e2e.py`

## Testing
1. Delete alpine image locally: `docker rmi alpine:3.19.1`
2. Run tests and verify image is pulled once
3. Run tests again and verify no re-pull (cached)
4. Verify test behavior is consistent across runs

## References
- Docker image tagging best practices
- Alpine Linux release cycle: https://alpinelinux.org/releases/
