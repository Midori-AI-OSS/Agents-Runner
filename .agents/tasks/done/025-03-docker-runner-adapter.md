# Implement Docker runner with adapter interface

**Parent Task:** 025-unify-runplan-pydantic.md

## Scope
Create docker runner following standardized flow with testable adapter interface.

## Actions
1. Create `agents_runner/planner/docker_adapter.py` with abstract interface:
   - `pull_image(image: str, timeout: int)`
   - `start_container(spec: DockerSpec) -> str` (returns container_id)
   - `wait_ready(container_id: str, timeout: int)`
   - `exec_run(container_id: str, exec_spec: ExecSpec) -> ExecutionResult`
   - `copy_from(container_id: str, src: Path, dst: Path)`
   - `stop_remove(container_id: str)`
2. Create `agents_runner/planner/runner.py` with `execute_plan(plan: RunPlan, adapter: DockerAdapter)`:
   - Pull image
   - Start container with keepalive command
   - Wait for ready state
   - Execute command via `docker exec`
   - Collect artifacts
   - Stop and remove container
3. Create concrete implementation using subprocess
4. Run linters

## Acceptance
- Clear adapter interface for testability
- Follows standardized flow from parent task
- No Qt imports
- Passes linting
- One focused commit: `[FEAT] Add Docker runner with adapter interface`

## Completion Notes
✓ Created `agents_runner/planner/docker_adapter.py` with abstract `DockerAdapter` interface and `ExecutionResult` class
✓ Created `agents_runner/planner/runner.py` with `execute_plan()` function following the standardized flow:
  - Pull image
  - Start container with keepalive
  - Wait for ready state
  - Execute via docker exec
  - Collect artifacts (with host path resolution)
  - Stop and remove container (always in finally block)
✓ Created `agents_runner/planner/subprocess_adapter.py` with concrete `SubprocessDockerAdapter` implementation
✓ Updated `agents_runner/planner/__init__.py` to export new components
✓ No Qt imports (headless)
✓ Passed ruff format and ruff check
✓ Committed with [FEAT] Add Docker runner with adapter interface (1e0d8c1)
