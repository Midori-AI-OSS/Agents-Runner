# Task: Move shell_templates.py from agents_runner/ui/ to agents_runner/core/

## Goal

Resolve UI package boundary violation by moving pure utility module `shell_templates.py` from the UI package to the core package, ensuring headless subsystems no longer import from UI.

## Rule Reference

**AGENTS.md Section:** "Organize the code as subsystem packages and subpackages"
> "All user-facing UI code lives under `agents_runner/ui/` (pages, widgets, styling, themes). Keep Qt isolated there: non-UI subsystems must not import Qt so a headless runner stays possible."

**Violation:** `agents_runner/ui/shell_templates.py` contains no Qt code but resides in UI package, forcing headless modules to import from UI.

## Scope

- Move `agents_runner/ui/shell_templates.py` to `agents_runner/core/shell_templates.py`
- Update imports in `agents_runner/docker/agent_worker.py`
- Update imports in `agents_runner/docker/preflight_worker.py`
- Verify no other modules import this file
- Ensure packaging still works

## Non-Goals

- Do not modify shell template functions themselves
- Do not add new functionality
- Do not refactor other UI modules

## Affected Files Inventory

**To Move:**
- `agents_runner/ui/shell_templates.py`

**Import Updates Needed:**
- `agents_runner/docker/agent_worker.py`
- `agents_runner/docker/preflight_worker.py`

**Verification:**
```bash
grep -r "shell_templates" agents_runner/ --include="*.py"
```

## Acceptance Criteria

- [ ] File `agents_runner/core/shell_templates.py` exists with content from original
- [ ] File `agents_runner/ui/shell_templates.py` deleted
- [ ] `agents_runner/docker/agent_worker.py` imports from `agents_runner.core.shell_templates`
- [ ] `agents_runner/docker/preflight_worker.py` imports from `agents_runner.core.shell_templates`
- [ ] No dangling imports to `ui.shell_templates` remain
- [ ] `agents_runner/core/__init__.py` exists
- [ ] `uv build` completes successfully
- [ ] `uv run ruff format .` passes
- [ ] `uv run ruff check .` passes
- [ ] Verification command returns zero matches

## Verification Commands

**Before changes (should fail):**
```bash
# Should find 2 imports from ui.shell_templates
grep -r "from agents_runner\.ui\.shell_templates" agents_runner/ --include="*.py"
```

**After changes (should pass):**
```bash
# Should find 0 imports from ui.shell_templates
grep -r "from agents_runner\.ui\.shell_templates" agents_runner/ --include="*.py"
# Expected: NO MATCHES

# Should find 2 imports from core.shell_templates
grep -r "from agents_runner\.core\.shell_templates" agents_runner/ --include="*.py"
# Expected: 2 matches (agent_worker.py, preflight_worker.py)

# Verify no headless imports from ui/
grep -r "from agents_runner\.ui" agents_runner/{core,docker,execution,environments,gh,preflights,security,stt,diagnostics} --include="*.py"
# Expected: NO MATCHES

# Verify packaging
uv build
# Expected: SUCCESS
```

## Definition of Done

- All acceptance criteria checked ✓
- All verification commands pass ✓
- Committed with message: `[REFACTOR] Move shell_templates from ui to core package` ✓
- Version bumped in `pyproject.toml` (TASK +1) ✓

## Completion Notes

Task completed successfully on 2025-02-01.

**Actions taken:**
1. Moved `agents_runner/ui/shell_templates.py` to `agents_runner/core/shell_templates.py`
2. Updated imports in 3 files:
   - `agents_runner/docker/agent_worker.py`
   - `agents_runner/docker/preflight_worker.py`
   - `agents_runner/ui/main_window_tasks_interactive_docker.py`
3. Deleted original file from UI package
4. Verified all changes with grep commands
5. Ran `uv run ruff format .` - passed
6. Ran `uv run ruff check .` - passed
7. Ran `uv build` - passed
8. Verified no headless imports from UI package remain
9. Bumped version from 0.1.0.6 to 0.1.0.7
10. Committed with message: `[REFACTOR] Move shell_templates from ui to core package`

**Verification results:**
- ✓ No imports from `agents_runner.ui.shell_templates` found in any files
- ✓ All imports now reference `agents_runner.core.shell_templates`
- ✓ No headless modules import from UI package
- ✓ Packaging works correctly
- ✓ All linters pass

The refactoring resolves the UI package boundary violation and ensures headless subsystems no longer import from the UI package.
