# Add unit tests for planner and runner

**Parent Task:** 025-unify-runplan-pydantic.md

## Scope
Add unit tests for `plan_run` and docker runner sequencing using fake adapter.

## Actions
1. Create `agents_runner/planner/tests/` package
2. Add `agents_runner/planner/tests/test_planner.py`:
   - Test `plan_run` with various `RunRequest` configurations
   - Test interactive vs non-interactive prompt handling
   - Test environment spec conversion to docker spec
3. Add `agents_runner/planner/tests/test_runner.py`:
   - Create fake/mock docker adapter
   - Test execution flow: pull → start → ready → exec → finalize
   - Test artifact collection
   - Test cleanup on success and failure
4. Run `uv run pytest`

## Acceptance
- All tests pass
- No actual Docker required for tests (use fake adapter)
- Tests are fast and deterministic
- Code coverage: aim for >80% of planner and runner modules
- Passes linting
- One focused commit: `[TEST] Add planner and runner unit tests`

## Completion
Task completed successfully. Created comprehensive unit tests for planner and runner modules with 26 passing tests covering all key functionality including plan generation, docker execution flow, artifact collection, and error handling scenarios. Tests use fake adapter for fast, deterministic testing without requiring Docker.
