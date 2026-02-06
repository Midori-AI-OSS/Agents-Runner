# Remove duplicate run planning codepaths

**Parent Task:** 025-unify-runplan-pydantic.md

## Scope
Clean up legacy per-mode "plan assembly" code now that callers are migrated.

## Actions
1. Identify duplicate run planning code from before migration:
   ```bash
   # Look for legacy planning patterns
   grep -r "plan_run\|docker.*start\|docker.*exec" --include="*.py" | grep -v "agents_runner/planner"
   ```
2. Remove dead code paths that are no longer called
3. Remove commented-out legacy code
4. Update any docstrings/comments that reference old flow
5. Run linters and full test suite

## Acceptance
- No duplicate planning logic remains
- All tests still pass
- No broken references to removed code
- Passes linting
- One focused commit: `[CLEANUP] Remove duplicate run planning codepaths`

## Completion Notes

**Completed:** 2024-02-06

**Changes Made:**
- Deleted `agents_runner/ui/main_window_tasks_interactive_docker.py` (707 lines) - completely replaced by `interactive_planner.py`
- Removed 7 dead methods from `agents_runner/docker/agent_worker_container.py`:
  - `_build_docker_run_args` - legacy docker command builder
  - `_build_env_args` - replaced by planner's env handling
  - `_build_port_args` - replaced by planner's port handling  
  - `_build_extra_mounts` - replaced by planner's mount handling
  - `_monitor_container` - replaced by unified runner
  - `_setup_desktop_port_mapping` - replaced by unified runner
  - `_cleanup_container` - replaced by unified runner cleanup
- Removed unused imports: selectors, subprocess, time, wrap_container_log, _run_docker, deduplicate_mounts
- Total reduction: 952 lines of duplicate code

**Verification:**
- ✅ Ruff format passed
- ✅ Ruff check passed (all checks passed)
- ✅ No broken references to removed code
- ✅ Commit: `[CLEANUP] Remove duplicate run planning codepaths` (3299472)
