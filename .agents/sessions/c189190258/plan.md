# E2E Test Implementation Plan

## Objective
Implement comprehensive end-to-end test for full task completion flow, mocking only agent output while using real orchestration components.

## Current State Analysis
- Repository: agents-runner (Python 3.13 with PySide6)
- Existing tests: test_env_parse.py, test_token_redaction.py (minimal coverage)
- Key components:
  - TaskSupervisor: orchestrates agent execution with retry/fallback
  - DockerAgentWorker: executes agent in container
  - Multiple task files created but not implemented
- Test framework: pytest with uv
- Environment: PixelArch container (permissive mode)

## Implementation Strategy

### Phase 1: Infrastructure Setup
1. Create test utilities for mocking subprocess calls
2. Create mock response patterns for agent output
3. Set up test fixtures for DockerRunnerConfig and supervisor

### Phase 2: Core E2E Test
1. Implement test_e2e_task_completion.py with:
   - Mock agent subprocess to return success responses
   - Use real TaskSupervisor orchestration
   - Verify full flow: start -> execute -> completion
   - Test artifact collection in /tmp/agents-artifacts
   - Validate metadata tracking

### Phase 3: Validation
1. Run existing tests to ensure no regressions
2. Run new e2e test
3. Run linters (ruff)
4. Fix any issues found

### Phase 4: Git Operations
1. Commit test implementation
2. Push to branch midoriaiagents/c189190258
3. Update PR metadata JSON

### Phase 5: Cleanup
1. Remove extra files from .agents/audit (keep AGENTS.md only)
2. Verify no extra docs in repo root
3. Final validation

## File Plan
- Create: `agents_runner/tests/test_e2e_task_completion.py` (~250 lines)
- Create: `agents_runner/tests/conftest.py` for shared fixtures (~100 lines)
- Update: `/tmp/codex-pr-metadata-c189190258.json`

## Testing Approach
- Mock only: subprocess.run/Popen calls for agent execution
- Real components: TaskSupervisor, error classification, retry logic, callbacks
- Validate: exit codes, artifacts, metadata, state transitions
- Use /tmp/agents-artifacts for all test artifacts

## Success Criteria
- [ ] Test file created and passes
- [ ] Mocks only agent output, uses real orchestration
- [ ] All existing tests still pass
- [ ] Linters pass (ruff)
- [ ] Committed with proper message format
- [ ] Branch pushed
- [ ] PR metadata updated
- [ ] Cleanup completed
