# Deep audit: Task 026 agent system plugins - AUDIT FAILED

**Audit Date:** 2025-02-06  
**Result:** ❌ Task requires revision  
**Full Report:** `/tmp/agents-artifacts/6f001f55-task-026-audit.md`

## Summary

The plugin system architecture is well-designed, but the migration from hardcoded agent logic is **incomplete**. Tests pass and code quality is excellent, but significant hardcoded string-based branching remains in the UI layer.

**Score: 21/25 (84%)** - Core plugin system passes all checks, but legacy hardcoded logic persists.

## Critical Issues Found

### 1. Hardcoded Agent Logic in UI Settings ❌
**File:** `agents_runner/ui/main_window_settings.py` (lines 108-135, 195-218)

Extensive if/elif chains for agent-specific behavior:
- Config key mapping (lines 110-126)
- Default interactive commands (lines 130-135) 
- Config directory resolution (lines 200-216)

**Impact:** Violates plugin abstraction. Adding new agents requires UI code changes.

### 2. Hardcoded Display Mappings ❌
**File:** `agents_runner/agent_display.py`

Display names and GitHub URLs hardcoded in dictionaries instead of plugin metadata.

### 3. Legacy "host_codex_dir" References ❌
Found in 9+ files across docker/, environments/, and config modules. "codex" is treated as the default agent system.

### 4. Missing Plugin System Tests ⚠️
No tests in `agents_runner/agent_systems/` directory. Plugin loading, registration, and validation not directly tested.

## What Works Well ✅

- Plugin system architecture (models, registry, base class)
- All 4 plugins properly implemented (codex, claude, copilot, gemini)
- Integration with unified planner works correctly
- All 26 planner tests pass
- Linting and type checking clean
- No Qt imports in plugin system (proper separation)
- Safe plugin discovery with error handling
- Plugin capabilities properly respected

## Required Actions

### Must Fix (Critical)
1. Remove all hardcoded agent string branching from UI settings
2. Move agent-specific defaults to plugin metadata
3. Refactor display name/URL mappings to use plugin data
4. Eliminate host_codex_dir - use generic config path mechanism

### Should Fix (High Priority)
5. Add plugin system tests (test_registry.py)
6. Add plugin development documentation

### Nice to Have (Medium Priority)  
7. Move rate limits to plugin capabilities
8. Document or fix hardcoded theme base colors

## Next Steps

1. Extend `AgentSystemPlugin` model with display metadata fields
2. Refactor `main_window_settings.py` to query plugins instead of string branching
3. Rename codex-specific paths to generic equivalents
4. Add comprehensive registry tests
5. Re-run audit to verify fixes

## Files Needing Updates

- `agents_runner/ui/main_window_settings.py` (primary issue)
- `agents_runner/agent_display.py`
- `agents_runner/docker/*` (9 files with host_codex_dir)
- `agents_runner/core/agent/rate_limit.py`
- `agents_runner/agent_systems/models.py` (add display metadata)

---

**Auditor Note:** The foundation is excellent. Completing the migration by eliminating the remaining hardcoded logic will result in a production-ready, fully extensible plugin system.
