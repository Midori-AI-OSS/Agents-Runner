# Task: Add Missing __init__.py Files to Python Packages

## Goal

Fix packaging hygiene by adding `__init__.py` files to two directories with Python modules that are missing them.

## Rule Reference

**AGENTS.md Section:** "Packaging (Hatchling)"
> "Any new importable directory under `agents_runner/` must include an `__init__.py`."

**Violation:** `agents_runner/diagnostics/` and `agents_runner/tests/` contain Python files but lack `__init__.py`.

## Scope

- Create `agents_runner/diagnostics/__init__.py`
- Create `agents_runner/tests/__init__.py`
- Verify packaging works correctly

## Non-Goals

- Do not modify existing Python modules
- Do not add package-level exports unless needed
- Do not reorganize package structure

## Affected Files Inventory

**To Create:**
- `agents_runner/diagnostics/__init__.py` (empty or minimal)
- `agents_runner/tests/__init__.py` (empty or minimal)

**Existing Modules in These Directories:**
```bash
ls agents_runner/diagnostics/*.py
ls agents_runner/tests/*.py
```

## Acceptance Criteria

- [ ] File `agents_runner/diagnostics/__init__.py` exists
- [ ] File `agents_runner/tests/__init__.py` exists
- [ ] Files can be empty or contain minimal package docstrings
- [ ] `uv build` completes successfully
- [ ] `uv run ruff format .` passes
- [ ] `uv run ruff check .` passes
- [ ] Verification script returns no missing `__init__.py` files

## Verification Commands

**Before changes (should fail):**
```bash
python3 - <<'PY'
from pathlib import Path
root = Path("agents_runner")
missing = []
for directory in root.rglob("*"):
    if not directory.is_dir():
        continue
    if directory.name == "__pycache__":
        continue
    has_py = any(p.suffix == ".py" for p in directory.iterdir() if p.is_file())
    if not has_py:
        continue
    if not (directory / "__init__.py").exists():
        missing.append(str(directory))
print("\n".join(sorted(missing)))
PY
# Expected: agents_runner/diagnostics, agents_runner/tests
```

**After changes (should pass):**
```bash
python3 - <<'PY'
from pathlib import Path
root = Path("agents_runner")
missing = []
for directory in root.rglob("*"):
    if not directory.is_dir():
        continue
    if directory.name == "__pycache__":
        continue
    has_py = any(p.suffix == ".py" for p in directory.iterdir() if p.is_file())
    if not has_py:
        continue
    if not (directory / "__init__.py").exists():
        missing.append(str(directory))
print("\n".join(sorted(missing)))
PY
# Expected: NO OUTPUT

# Verify packaging
uv build
# Expected: SUCCESS
```

## Implementation Notes

**Minimal `__init__.py` Content (Recommended):**
```python
"""Diagnostics subsystem."""
```

or simply create empty files:
```bash
touch agents_runner/diagnostics/__init__.py
touch agents_runner/tests/__init__.py
```

## Definition of Done

- All acceptance criteria checked
- All verification commands pass
- Committed with message: `[FIX] Add missing __init__.py to diagnostics and tests packages`
- Version bumped in `pyproject.toml` (TASK +1)

## Completion Notes

**Status:** COMPLETED

**Date:** 2025-02-01

**Actions Taken:**
1. Created `agents_runner/diagnostics/__init__.py` with minimal docstring
2. Created `agents_runner/tests/__init__.py` with minimal docstring
3. Verified all packaging requirements:
   - No missing __init__.py files found in verification script
   - `uv build` completed successfully
   - `ruff format .` passed (156 files left unchanged)
   - `ruff check .` passed (all checks passed)
4. Committed changes with message: `[FIX] Add missing __init__.py to diagnostics and tests packages`
5. Bumped version from 0.1.0.3 to 0.1.0.4
6. Committed version bump with message: `[VERSION] Bump to 0.1.0.4 after task completion`

**Result:** All acceptance criteria met. Package hygiene restored.
