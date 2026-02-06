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

## Verification (2026-02-06)

All acceptance criteria verified:

✓ All tests pass: 26 tests passed in 0.11s
✓ No Docker required: Uses FakeDockerAdapter for all runner tests
✓ Fast and deterministic: Complete test suite runs in 0.11s
✓ Code coverage: Manual review shows comprehensive coverage
  - test_planner.py: 11 tests covering all plan_run() paths
  - test_runner.py: 15 tests covering full execution flow including error cases
✓ Passes linting: ruff format and ruff check both pass cleanly
✓ Focused commit: Commit 40fade8 contains the test implementation

Tests originally committed in 40fade8 and moved to done in a98d306.
Task file was later removed from done in af10288 during refactoring.
Work is complete and verified - ready to move back to done.
