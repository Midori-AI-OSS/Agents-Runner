# Deep audit: Task 026 agent system plugins - AUDIT FAILED → ADDRESSED

**Audit Date:** 2025-02-06  
**Resolution Date:** 2025-02-06  
**Result:** ✅ Critical issues addressed  
**Full Report:** `/tmp/agents-artifacts/6f001f55-task-026-audit.md`

## Summary

The plugin system architecture is well-designed, but the migration from hardcoded agent logic was **incomplete**. Tests pass and code quality is excellent, but significant hardcoded string-based branching remained in the UI layer.

**Original Score: 21/25 (84%)** - Core plugin system passed all checks, but legacy hardcoded logic persisted.

## Critical Issues Found → FIXED

### 1. Hardcoded Agent Logic in UI Settings ❌ → ✅ FIXED
**File:** `agents_runner/ui/main_window_settings.py` (lines 108-135, 195-218)

Extensive if/elif chains for agent-specific behavior:
- Config key mapping (lines 110-126) → **FIXED**: Now uses plugin registry
- Default interactive commands (lines 130-135) → **FIXED**: Uses plugin.default_interactive_command
- Config directory resolution (lines 200-216) → **FIXED**: Uses plugin metadata

**Impact:** Violates plugin abstraction. Adding new agents requires UI code changes. → **RESOLVED**

### 2. Hardcoded Display Mappings ❌ → ✅ FIXED
**File:** `agents_runner/agent_display.py`

Display names and GitHub URLs hardcoded in dictionaries instead of plugin metadata. → **FIXED**: Now queries plugin registry

### 3. Legacy "host_codex_dir" References ❌ → ⚠️ ACKNOWLEDGED
Found in 9+ files across docker/, environments/, and config modules. "codex" is treated as the default agent system.

**Status:** Not addressed in this task. Field name remains for backward compatibility. The critical issue (hardcoded UI logic) is fixed. Lower-level field naming is a separate concern.

### 4. Missing Plugin System Tests ⚠️ → NOT IN SCOPE
No tests in `agents_runner/agent_systems/` directory. Plugin loading, registration, and validation not directly tested.

**Status:** Not addressed. Should be a separate task. All 26 planner tests still pass.

## What Works Well ✅

- Plugin system architecture (models, registry, base class)
- All 4 plugins properly implemented (codex, claude, copilot, gemini)
- Integration with unified planner works correctly
- All 26 planner tests pass
- Linting and type checking clean
- No Qt imports in plugin system (proper separation)
- Safe plugin discovery with error handling
- Plugin capabilities properly respected

## Actions Taken

### Completed (Critical)
1. ✅ Extended `AgentSystemPlugin` model with display metadata fields (display_name, github_url, config_dir_name, default_interactive_command)
2. ✅ Updated all 4 plugins with metadata
3. ✅ Refactored `agent_display.py` to query plugins instead of hardcoded dicts
4. ✅ Refactored `main_window_settings.py` methods to use plugin metadata:
   - `_interactive_command_key()` 
   - `_host_config_dir_key()`
   - `_default_interactive_command()`
   - `_resolve_config_dir_for_agent()`
   - `_apply_settings()` - now dynamically discovers plugins
   - `_sanitize_interactive_command_value()` - uses plugin registry
5. ✅ All tests pass (26/26 planner tests)
6. ✅ Ruff format and check pass

### Not Addressed (Out of Scope for Minimal Changes)
- host_codex_dir field renaming (would require extensive changes, breaks backward compatibility)
- Plugin system tests (should be separate task)
- Rate limit migration to plugins (should be separate task)
- Plugin development documentation (should be separate task)

## Files Updated

- `agents_runner/agent_systems/models.py` - Added display metadata fields
- `agents_runner/agent_systems/codex/plugin.py` - Added metadata
- `agents_runner/agent_systems/claude/plugin.py` - Added metadata
- `agents_runner/agent_systems/copilot/plugin.py` - Added metadata
- `agents_runner/agent_systems/gemini/plugin.py` - Added metadata
- `agents_runner/agent_display.py` - Refactored to use plugin registry
- `agents_runner/ui/main_window_settings.py` - Refactored all hardcoded agent logic to use plugins

---

**Resolution:** The critical hardcoded logic in the UI layer has been eliminated. Adding new agent systems no longer requires modifying UI code - only adding a new plugin with metadata. The plugin abstraction is now properly respected throughout the UI layer.
