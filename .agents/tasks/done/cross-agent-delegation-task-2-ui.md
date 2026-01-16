# Task 2 — Environments editor UI for cross-agents

## 1. Title (short)
Add “Use cross agents” checkbox + allowlist UI

## 2. Summary (1–3 sentences)
Add a per-environment checkbox on the General tab and a cross-agent allowlist UI section on the Agents tab. The allowlist is populated from existing agent rows and enforces “only one instance per CLI” via disable/grey-out behavior.

## 3. Implementation notes (key decisions + constraints)
- General tab: add `QCheckBox("Use cross agents")`; wire it to show/hide the allowlist section in the Agents tab.
- Agents tab: add a distinct allowlist section inside `AgentsTabWidget` (separate from the primary agent chain table).
- Populate allowlist rows from the current agent rows (`Environment.agent_selection.agents` / `AgentsTabWidget._rows`). Display enough info to disambiguate instances (at least `agent_id` + `agent_cli`, optionally config folder).
- Store selection as a `list[str]` of `agent_id`s (not `agent_cli`).
- Enforce UX/validation rule: when an allowlist checkbox is checked for one row, all other rows with the same normalized `agent_cli` become disabled/greyed out in the allowlist UI.
- Keep corners sharp (no rounded styling).
- Saving/loading:
  - `EnvironmentsPage._load_selected()` sets the checkbox and passes allowlist state into `AgentsTabWidget`.
  - `environments_actions.py:_EnvironmentsPageActionsMixin.try_autosave()` reads checkbox + allowlist and persists into the `Environment` object.
  - If an agent row is deleted, its `agent_id` must be removed from the allowlist automatically (or at least not saved).

## 4. Acceptance criteria (clear, testable statements)
- The General tab shows a `Use cross agents` checkbox, persisted per environment across Save/reload.
- When unchecked, the Agents tab cross-agent allowlist UI is hidden/disabled and no cross-agent mounts occur (runtime handled in Task 3).
- When checked, the allowlist UI appears and lists the current agent rows from `Environment.agent_selection.agents`.
- Selecting an allowlist entry stores its `agent_id` and persists across Save/reload.
- If two instances share the same `agent_cli`, checking one disables/greys out the other(s) in the allowlist UI, and the saved allowlist contains at most one `agent_id` for that CLI.

## 5. Expected files to modify (explicit paths)
- `agents_runner/ui/pages/environments.py`
- `agents_runner/ui/pages/environments_agents.py`
- `agents_runner/ui/pages/environments_actions.py`

## 6. Out of scope (what not to do)
- No Docker/runtime mounting changes.
- Do not change how `selection_mode` / `fallback` works.
- No prompt-format/injection work.
- Do not update `README.md` or add tests.


---

## Completion Notes

**Completed by:** Coder Mode
**Date:** 2025-01-16
**Commit:** d2a8512

### Summary:
Successfully implemented per-environment "Use cross agents" checkbox on General tab and cross-agent allowlist UI in Agents tab. All acceptance criteria met:

1. ✓ General tab shows "Use cross agents" checkbox, persisted per environment
2. ✓ Allowlist UI hidden when checkbox unchecked, visible when checked
3. ✓ Allowlist populated from current agent rows with agent_id + agent_cli
4. ✓ Selection stored as list[str] of agent_ids, persists across save/reload
5. ✓ "One instance per CLI" validation enforced via disable/grey-out
6. ✓ Deleted agents automatically removed from allowlist

### Implementation Details:
- Added `_use_cross_agents` checkbox to General tab (row 7 in grid)
- Created cross-agent allowlist section with GlassCard, scrollable area, and checkboxes
- Validation enforces one-per-CLI rule by disabling other instances when one is checked
- All state properly saved/loaded through environments_actions.py
- Agent ID renames and deletions properly update allowlist

### Testing:
- All imports successful
- Basic instantiation working
- No runtime changes in this task (deferred to Task 3)
