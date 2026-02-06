# Add Pydantic run-planning models

**Parent Task:** 025-unify-runplan-pydantic.md

## Scope
Add `pydantic` dependency and introduce core run-planning models in a new headless package.

## Actions
1. Add `pydantic>=2.0` to dependencies in `pyproject.toml`
2. Create `agents_runner/planner/` package with `__init__.py`
3. Create `agents_runner/planner/models.py` with Pydantic models:
   - `MountSpec`
   - `TimeoutSpec`
   - `DockerSpec`
   - `ExecSpec`
   - `ArtifactSpec`
   - `EnvironmentSpec`
   - `RunRequest`
   - `RunPlan`
4. Ensure no Qt imports in this package (headless)
5. Add field validators for Path types to ensure they are absolute paths where required
6. Run `uv run --group lint ruff format .` and `uv run --group lint ruff check .`

## Acceptance
- All models defined per prototype in parent task
- Package is headless (no Qt dependency)
- Passes linting
- One focused commit: `[FEAT] Add Pydantic run-planning models`

## Completion Notes
✓ Added `pydantic>=2.0` to dependencies in pyproject.toml
✓ Created `agents_runner/planner/` package with __init__.py
✓ Created `agents_runner/planner/models.py` with all required Pydantic models:
  - MountSpec (with path validation)
  - TimeoutSpec
  - DockerSpec (with workdir validation)
  - ExecSpec (with cwd validation)
  - ArtifactSpec
  - EnvironmentSpec
  - RunRequest (with host path validation)
  - RunPlan
✓ Package is headless (no Qt imports)
✓ All models have field validators for absolute path requirements
✓ Passed ruff format and ruff check
✓ Committed as: [FEAT] Add Pydantic run-planning models

**Completed:** 2024-02-06
