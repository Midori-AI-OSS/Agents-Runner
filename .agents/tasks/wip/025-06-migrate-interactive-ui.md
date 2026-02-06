# Migrate interactive UI path to unified planner

**Parent Task:** 025-unify-runplan-pydantic.md

## Scope
Switch interactive UI path to use shared planner/runner.

## Actions
1. Locate existing interactive task execution code in `agents_runner/ui/` (check task-related UI modules and terminal widgets)
2. Refactor UI to:
   - Build `RunRequest` with `interactive=True`
   - Call `plan_run(request)` to get `RunPlan`
   - Use runner for pull → start → ready
   - Open terminal and attach with `docker exec -it`
   - Use runner for finalization (artifact collection, cleanup)
3. UI stays responsible only for terminal rendering
4. Ensure desktop-enabled and desktop-disabled paths both work
5. Run linters and manual verification

## Manual Test Checklist
- [ ] Desktop mode: X11 forwarding works, UI elements display correctly
- [ ] Headless mode: Terminal attaches without X11
- [ ] Image pull happens before terminal window opens
- [ ] Terminal attaches successfully and is interactive
- [ ] Container cleanup occurs after terminal closes
- [ ] Artifacts are collected correctly

## Acceptance
- Interactive runs use unified flow
- Pull happens before terminal window opens
- Desktop mode works correctly
- No Qt imports outside `agents_runner/ui/`
- Manual test: run interactive task with/without desktop
- Passes linting
- One focused commit: `[REFACTOR] Migrate interactive UI to unified planner`
