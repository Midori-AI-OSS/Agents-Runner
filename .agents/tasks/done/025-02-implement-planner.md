# Implement run planner function

**Parent Task:** 025-unify-runplan-pydantic.md

## Scope
Implement the `plan_run` function that converts `RunRequest` to `RunPlan`.

## Actions
1. Create `agents_runner/planner/planner.py`
2. Implement `plan_run(request: RunRequest) -> RunPlan`:
   - Convert `EnvironmentSpec` to `DockerSpec`
   - Build `ExecSpec` for agent command
   - Handle interactive vs non-interactive prompt prefix
   - Resolve mounts and environment variables
   - Keep function pure (no subprocess/filesystem calls)
3. Add docstrings explaining the planning logic
4. Run linters

## Acceptance
- `plan_run` is pure function (no side effects)
- Handles both `interactive=True` and `interactive=False`
- Interactive runs get guardrail prefix: `do not take action, just review the needed files and check your preflight if the repo has those and then standby`
- Passes linting
- One focused commit: `[FEAT] Implement run planner function`

## Completion Note
Completed successfully. Created `agents_runner/planner/planner.py` with pure `plan_run()` function that converts `RunRequest` to `RunPlan`. Function handles both interactive and non-interactive modes, builds Docker specs with mounts and environment variables, and composes prompts with guardrail prefix for interactive runs. All acceptance criteria met.
