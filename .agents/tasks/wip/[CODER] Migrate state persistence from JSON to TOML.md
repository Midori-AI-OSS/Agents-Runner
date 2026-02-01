# Task: Migrate State Persistence from JSON to TOML

## Goal

Resolve config hygiene violation by migrating state and metadata persistence from JSON to TOML format, aligning with AGENTS.md requirements.

## Rule Reference

**AGENTS.md Section:** "Configuration"
> "Source of truth is TOML parsed with `tomli` and written with `tomli-w` (no JSON config files, no env-driven config)."

**Violation:** `agents_runner/persistence.py` and `agents_runner/pr_metadata.py` use JSON for configuration and state storage.

## Scope

- Migrate `agents_runner/persistence.py` from JSON to TOML
- Migrate `agents_runner/pr_metadata.py` from JSON to TOML
- Update file extensions from `.json` to `.toml`
- Update all read/write operations

## Non-Goals

- Do not change diagnostic data formats (crash reports can stay JSON)
- Do not change artifact metadata (interchange format, JSON acceptable)
- Do not change the API/function signatures
- Do not add new features

## Exceptions (JSON Still Allowed)

These files can continue using JSON (diagnostic/interchange data, not config):
- `agents_runner/artifacts.py` (artifact metadata)
- `agents_runner/diagnostics/crash_reporting.py` (crash dumps)

## Affected Files Inventory

**To Modify:**
- `agents_runner/persistence.py`: Replace `json.dump/load` with `tomli_w.dump/tomli.load`
- `agents_runner/pr_metadata.py`: Replace `json.dump/load` with `tomli_w.dump/tomli.load`

**State File Paths to Update:**
- `state.json` → `state.toml`
- `codex-pr-metadata-*.json` → `codex-pr-metadata-*.toml`
- `pr-metadata-*.json` → `pr-metadata-*.toml`
- `github-context-*.json` → `github-context-*.toml`

**Dependencies:**
```bash
# Verify tomli and tomli-w are in pyproject.toml
grep -E "(tomli|tomli-w)" pyproject.toml
```

## Acceptance Criteria

- [ ] `persistence.py` uses `tomli.load` and `tomli_w.dump`
- [ ] `pr_metadata.py` uses `tomli.load` and `tomli_w.dump`
- [ ] All file extensions changed from `.json` to `.toml`
- [ ] Path generation functions updated
- [ ] All state read/write operations work with TOML
- [ ] No JSON import/usage in persistence.py (except error handling if needed)
- [ ] No JSON import/usage in pr_metadata.py (except error handling if needed)
- [ ] `uv run ruff format .` passes
- [ ] `uv run ruff check .` passes
- [ ] If tests exist, `uv run pytest` passes

## Verification Commands

**Before changes (should fail):**
```bash
# Should find json.dump/load in state/config modules
rg -n "\\bjson\\.(dump|dumps|load|loads)\\b" agents_runner/persistence.py agents_runner/pr_metadata.py
# Expected: 10+ matches

# Should find .json extensions
rg -n "\\.json\\b" agents_runner/persistence.py agents_runner/pr_metadata.py
# Expected: Multiple matches
```

**After changes (should pass):**
```bash
# Should NOT find json module usage in state/config modules
rg -n "\\bjson\\.(dump|dumps|load|loads)\\b" agents_runner/persistence.py agents_runner/pr_metadata.py
# Expected: NO MATCHES

# Should find tomli/tomli_w usage
rg -n "\\btomli(_w)?\\.(dump|load)\\b" agents_runner/persistence.py agents_runner/pr_metadata.py
# Expected: 10+ matches

# Should find .toml extensions
rg -n "\\.toml\\b" agents_runner/persistence.py agents_runner/pr_metadata.py
# Expected: Multiple matches

# Verify other JSON usage is in exceptions only
rg -n "\\bjson\\." agents_runner --glob '!agents_runner/artifacts.py' --glob '!agents_runner/diagnostics/**'
# Expected: Minimal matches (only interchange/diagnostic data)
```

## Implementation Notes

**JSON to TOML Conversion:**

Before (JSON):
```python
import json

with open(path, "w") as f:
    json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=True)

with open(path, "r") as f:
    payload = json.load(f)
```

After (TOML):
```python
import tomli
import tomli_w

with open(path, "wb") as f:
    tomli_w.dump(payload, f)

with open(path, "rb") as f:
    payload = tomli.load(f)
```

**Key Differences:**
- TOML requires binary mode (`"wb"`, `"rb"`)
- `tomli_w.dump` doesn't have `indent` or `sort_keys` params (TOML handles formatting)
- TOML has stricter type requirements (may need data structure adjustments)

## Migration Strategy

1. **Add imports** to both files: `import tomli`, `import tomli_w`
2. **Update file path functions** to return `.toml` extensions
3. **Update write operations** to use binary mode and `tomli_w.dump`
4. **Update read operations** to use binary mode and `tomli.load`
5. **Test locally** to ensure data serialization works
6. **Handle backward compatibility** if needed (read old .json files, write .toml)

## Definition of Done

- All acceptance criteria checked
- All verification commands pass
- Committed with message: `[REFACTOR] Migrate state persistence from JSON to TOML format`
- Version bumped in `pyproject.toml` (TASK +1)
