# Migrate non-interactive task execution to unified planner

**Parent Task:** 025-unify-runplan-pydantic.md

## Scope
Switch non-interactive task execution to use the shared planner/runner.

## Actions
1. Locate existing non-interactive task execution code (likely in `agents_runner/tasks/` or similar executor module)
2. Refactor to build `RunRequest` from inputs
3. Call `plan_run(request)` to get `RunPlan`
4. Call `execute_plan(plan, concrete_adapter)` to run
5. Update state management and artifact collection to use runner outputs
6. Keep changes minimal - avoid drive-by refactors
7. Run linters and manual verification

## Manual Test Checklist
- [ ] Task completes successfully with exit code 0
- [ ] Artifacts are collected correctly
- [ ] Container is removed after execution
- [ ] State updates reflect completion
- [ ] Error handling works (test with failing task)

## Acceptance
- Non-interactive runs use unified flow
- Pull happens before execution (no pre-pull pinging)
- Cleanup is reliable (stop and remove container)
- Manual test: run agent task and verify correct behavior
- Passes linting
- One focused commit: `[REFACTOR] Migrate non-interactive execution to unified planner`
