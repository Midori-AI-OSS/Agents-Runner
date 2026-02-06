# Migrate planner to use agent system plugins

**Parent Task:** 026-agent-system-plugins.md

## Scope
Update run planner from task 025 to call agent system plugins instead of string branching.

## Actions
1. Update `agents_runner/planner/planner.py` `plan_run` function:
   - Get plugin from registry by `system_name`
   - Build `AgentSystemRequest` from `RunRequest`
   - Call `plugin.plan(request)` to get `AgentSystemPlan`
   - Use plugin outputs for exec argv, mounts, prompt delivery
2. Remove string-based branching on agent system names
3. Handle interactive support policy from plugin capabilities
4. Ensure integration with `EnvironmentSpec` still works
5. Update tests to work with plugin system
6. Run linters and test suite

## Acceptance
- Planner queries plugin system instead of hardcoded logic
- All existing agent systems work correctly
- Tests pass
- Passes linting
- One focused commit: `[REFACTOR] Migrate planner to use agent system plugins`

## Completion Notes
✅ Task completed successfully. The planner now uses the agent system plugin registry:
- Removed dependency on `build_noninteractive_cmd` and `container_config_dir`
- Planner queries plugins via `get_plugin(system_name)` and calls `plugin.plan()`
- Converts plugin outputs (ExecSpec, MountSpec) to planner models
- Interactive support is enforced via plugin capabilities
- All 11 tests pass after updating to account for plugin-specific mounts
- Linting passes (ruff format + ruff check)
- Committed as: `[REFACTOR] Migrate planner to use agent system plugins`
