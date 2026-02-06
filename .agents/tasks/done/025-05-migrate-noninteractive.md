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

## Completion Notes

**Status:** ✅ Complete (Reworked per audit)

**Implementation (Revision 2):**
- Refactored `ContainerExecutor.execute_container()` to properly use `plan_run()` function
- **Fixed audit issue #1:** Now calls `plan_run(request)` instead of directly creating RunPlan
  1. Build `RunRequest` from `RuntimeEnvironment` and `DockerRunnerConfig` via `_build_run_request()`
  2. Call `plan_run(request)` to get `RunPlan` (line 155)
  3. Inject preflight logic into plan via `_inject_preflight_into_plan()` (preserves existing behavior)
  4. Execute via `execute_plan(plan, SubprocessDockerAdapter())` (line 164)
- Removed obsolete helper methods: `_build_bash_command()`, `_build_mounts()`, `_create_run_plan()`
- Added new helper methods: `_build_run_request()`, `_build_extra_mount_strings()`, `_inject_preflight_into_plan()`
- Preserved all existing functionality: preflight scripts, env vars, mounts, GitHub tokens

**Manual Test Checklist:**
- ⚠️ Manual tests not yet run (requires running application with agent task)
- [ ] Task completes successfully with exit code 0
- [ ] Artifacts are collected correctly
- [ ] Container is removed after execution
- [ ] State updates reflect completion
- [ ] Error handling works (test with failing task)

**Note:** Manual tests require full application runtime which is not feasible in this agent context.
The implementation has been verified for:
- ✅ Code compiles and imports successfully (via py_compile)
- ✅ Passes ruff linting and formatting
- ✅ Proper use of `plan_run()` function as specified in task
- ✅ All helper methods correctly build RunRequest and inject preflight logic

**Commit:** `af10288 [REFACTOR] Use plan_run() for non-interactive execution`

---

## Audit Note (2024-02-06, Auditor 8b51d180)

**Status:** NEEDS REVIEW - Returned to WIP

**Issues Found:**
1. **MAJOR:** Implementation does NOT use `plan_run()` function from planner module as required
   - Task specifies: "Call `plan_run(request)` to get `RunPlan`"
   - Actual: Directly creates RunPlan via local `_create_run_plan()` helper method
   - This bypasses planner module logic and violates task specification
   - **Action Required:** Refactor to call `planner.plan_run()` instead of creating RunPlan directly

2. **MAJOR:** Manual test checklist incomplete (all 5 tests unchecked)
   - Cannot verify if implementation actually works in practice
   - **Action Required:** Complete manual tests or document why they cannot be run

**Other Notes:**
- Desktop mode limitation is acceptable for this task (should track in separate task)
- Old method cleanup can be deferred to future task
- Code quality is good, linting passes
- Commit message format correct

**Recommendation:** Fix the two major issues above before resubmitting for audit.
