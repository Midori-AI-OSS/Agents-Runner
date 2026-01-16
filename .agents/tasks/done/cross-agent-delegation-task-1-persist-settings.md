# Task 1 — Persist cross-agent delegation settings

## 1. Title (short)
Persist cross-agent toggle + allowlist in `Environment`

## 2. Summary (1–3 sentences)
Add new per-environment fields to store whether cross-agent delegation is enabled and which agent instances are allowlisted. Persist them through environment JSON load/save with backward-compatible defaults and minimal validation.

## 3. Implementation notes (key decisions + constraints)
- Keep `ENVIRONMENT_VERSION` unchanged (loader rejects version mismatches).
- Add `Environment.use_cross_agents: bool = False` and `Environment.cross_agent_allowlist: list[str] = field(default_factory=list)` (names can vary but must map cleanly to JSON).
- Store allowlist entries by `AgentInstance.agent_id` (never by `agent_cli`).
- Validation on deserialize (and optionally before serialize):
  - Coerce to `list[str]`, strip empties, de-dupe.
  - If `env.agent_selection` is missing/empty, force allowlist to empty.
  - Filter unknown `agent_id`s (must exist in `Environment.agent_selection.agents`).
  - Enforce “max 1 allowlisted per `agent_cli`” by keeping the first occurrence per normalized CLI and dropping the rest.
- Do not conflate with `AgentSelection.selection_mode` or `agent_fallbacks` (no changes to selection behavior).

## 4. Acceptance criteria (clear, testable statements)
- Loading an environment JSON without the new keys results in `use_cross_agents == False` and `cross_agent_allowlist == []`.
- Saving an environment with the new fields round-trips (save → load preserves values) when the allowlist is valid.
- Invalid allowlist payloads (wrong type, unknown IDs, duplicates, multiple IDs for the same CLI) are sanitized to a valid stored list.
- `cross_agent_allowlist` is always stored/loaded as agent instance IDs (`AgentInstance.agent_id`).

## 5. Expected files to modify (explicit paths)
- `agents_runner/environments/model.py`
- `agents_runner/environments/serialize.py`

## 6. Out of scope (what not to do)
- No UI changes.
- No runtime/Docker changes.
- Do not change `ENVIRONMENT_VERSION`.
- Do not update `README.md` or add tests.


---

## Completion Note

**Status:** ✅ Complete  
**Completed:** $(date -u +"%Y-%m-%d %H:%M:%S UTC")

### Implementation Summary
Added `use_cross_agents` (bool) and `cross_agent_allowlist` (list[str]) fields to Environment dataclass with full serialization/deserialization support and validation logic.

### Changes Made
- **model.py**: Added two new fields to Environment dataclass
- **serialize.py**: 
  - Implemented `_validate_cross_agent_allowlist()` helper with comprehensive validation
  - Updated `_environment_from_payload()` to deserialize and validate new fields
  - Updated `serialize_environment()` to serialize with pre-save validation

### Validation Rules Implemented
1. Coerce to list[str], strip empties, de-dupe
2. Force empty list if no agents configured
3. Filter unknown agent_ids (must exist in agent_selection.agents)
4. Enforce max 1 allowlisted per agent_cli (keeps first occurrence per normalized CLI)

### Testing
All acceptance criteria verified:
- ✅ Backward compatibility with missing keys
- ✅ Round-trip save/load preservation
- ✅ Invalid payload sanitization
- ✅ Agent ID (not CLI) storage format

No issues found. Ready for integration.
