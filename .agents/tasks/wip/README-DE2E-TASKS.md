# Docker E2E Test Isolation Tasks - Quick Reference

**Created:** 2026-02-03  
**Purpose:** Fix docker e2e tests to ensure each test spins a fresh container  
**Total Tasks:** 7  
**Estimated Effort:** 2.5-4 hours

**Important:** Follow AGENTS.md policies:
- Modify existing tests only (no new tests unless explicitly requested, per line 78-83)
- Minimal documentation (prefer code and inline comments, per line 43-44)
- Use existing `_run_docker` helper from `agents_runner.docker.process` where applicable

## Quick Start

Pick any task from below and implement it. High-priority tasks should be done first.

## Task List

### 🔴 High Priority (Critical for test isolation)

- **DE2E-001**: Verify Test Fixture Isolation ⏱️ 15-30 min
  - Verify pytest fixtures are function-scoped
  - Add assertions for unique task_id
  
- **DE2E-002**: Add Explicit Container Cleanup ⏱️ 30-45 min
  - Implement cleanup verification with finalizers
  - Add session-level cleanup for orphaned containers
  - Wait for container removal completion

### 🟡 Medium Priority (Enhanced isolation)

- **DE2E-003**: Enhance Container Name Uniqueness ⏱️ 20-30 min
  - Add test-specific prefixes to container names
  - Improve debuggability
  
- **DE2E-005**: Add Network and Volume Cleanup ⏱️ 30-45 min
  - Cleanup networks and volumes after tests
  - Prevent resource leaks
  
- **DE2E-006**: Ensure Parallel Test Safety ⏱️ 30-60 min
  - Verify pytest-xdist compatibility
  - Test with multiple workers
  
- **DE2E-007**: Add Pre-Test State Verification ⏱️ 20-30 min
  - Verify clean Docker state before tests
  - Auto-cleanup or fail-fast options

### 🟢 Low Priority (Nice to have)

- **DE2E-004**: Implement Test Image Management ⏱️ 30-45 min
  - Pin alpine version for reproducibility
  - Add session-scoped image management

## Recommended Order

1. DE2E-001 (Foundation)
2. DE2E-002 (Critical cleanup)
3. DE2E-007 (Early detection)
4. DE2E-003 (Better debugging)
5. DE2E-005 (Prevent leaks)
6. DE2E-006 (Performance)
7. DE2E-004 (Reproducibility)

## Testing After Each Task

```bash
# Run the docker e2e tests
uv run pytest agents_runner/tests/test_docker_e2e.py -v

# Check for leftover containers
docker ps -a | grep agents-runner

# Check for leftover networks
docker network ls | grep agents-runner

# Check for leftover volumes
docker volume ls | grep agents-runner
```

## Notes

- Each task is independent (but note dependencies in task files)
- All tasks have acceptance criteria
- Implementation notes provided in each file
- Follow AGENTS.md guidelines (test policy, doc policy, logging policy)
- Use existing helpers: `_run_docker`, `_inspect_state` from `agents_runner.docker.process`
- Commit early and often
