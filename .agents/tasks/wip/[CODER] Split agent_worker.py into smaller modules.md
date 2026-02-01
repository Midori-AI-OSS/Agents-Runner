# Task: Split agent_worker.py into Smaller Modules

## Goal

Resolve file size hard limit violation by splitting `agents_runner/docker/agent_worker.py` (1141 lines) into focused modules, each under the 600-line hard limit.

## Rule Reference

**AGENTS.MD Section:** "Development Basics"
> "Avoid monolith files: **soft max 300 lines per file**, **hard max 600 lines per file** (split modules/classes when approaching the soft limit)."

**Violation:** `agents_runner/docker/agent_worker.py` is 1141 lines (1.9x over hard limit).

## Scope

- Analyze `agent_worker.py` structure and responsibilities
- Split into 3-4 focused modules
- Update imports in dependent modules
- Maintain all existing functionality

## Non-Goals

- Do not change business logic
- Do not refactor function implementations
- Do not add new features
- Do not change public API

## Suggested Module Split

Based on file analysis, suggested split:

1. **`agent_worker_core.py`** (~300 lines): Main orchestration, worker class, lifecycle
2. **`agent_worker_docker.py`** (~300 lines): Docker container operations, exec commands
3. **`agent_worker_git.py`** (~250 lines): Git clone/update/branch operations
4. **`agent_worker_execution.py`** (~250 lines): Command execution, output handling

**Note:** Exact split should be determined after analyzing the file structure.

## Affected Files Inventory

**To Split:**
- `agents_runner/docker/agent_worker.py` (1141 lines)

**New Files to Create:**
- `agents_runner/docker/agent_worker_core.py`
- `agents_runner/docker/agent_worker_docker.py`
- `agents_runner/docker/agent_worker_git.py`
- `agents_runner/docker/agent_worker_execution.py`

**Potential Import Updates:**
```bash
# Find all imports of agent_worker
grep -r "from agents_runner.docker.agent_worker import\|import agents_runner.docker.agent_worker" agents_runner/ --include="*.py"
```

## Acceptance Criteria

- [ ] Original `agent_worker.py` split into 3-4 modules
- [ ] Each new module under 600 lines (hard limit)
- [ ] Each new module ideally under 300 lines (soft limit)
- [ ] All imports updated in dependent modules
- [ ] All existing functionality preserved
- [ ] `uv run ruff format .` passes
- [ ] `uv run ruff check .` passes
- [ ] `uv build` completes successfully
- [ ] Verification commands show no files over hard limit in docker/

## Verification Commands

**Before changes (should fail):**
```bash
wc -l agents_runner/docker/agent_worker.py
# Expected: 1141 lines (OVER 600 line hard limit)
```

**After changes (should pass):**
```bash
# No files over 600 lines in docker/
wc -l agents_runner/docker/*.py | awk '$1 > 600 {print}'
# Expected: NO OUTPUT

# Check all new files are under soft limit ideally
wc -l agents_runner/docker/agent_worker*.py | sort -n
# Expected: All under 600, most under 300 ideally

# Verify packaging
uv build
# Expected: SUCCESS
```

## Implementation Strategy

1. **Read and analyze** `agent_worker.py` structure
2. **Identify logical boundaries** (classes, function groups)
3. **Create new module files** with appropriate content
4. **Move functions/classes** to new modules
5. **Update cross-module imports** using relative or absolute imports
6. **Update dependent modules** that import from agent_worker
7. **Test import chain** works correctly
8. **Format and lint**
9. **Verify packaging**

## Definition of Done

- All acceptance criteria checked
- All verification commands pass
- Committed with message: `[REFACTOR] Split agent_worker.py into smaller focused modules`
- Version bumped in `pyproject.toml` (TASK +1)
