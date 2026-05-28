# Simplify Environments Agents Tab

## Files to modify
- `agents_runner/ui/pages/environments_agents.py`

## Actions

### 1. Reduce table columns
Current 8 columns (Priority, Agent, ID, Config folder, CLI Flags, Fallback, Cross, Remove) → 5 columns:
- Priority
- Config ID (QComboBox dropdown showing available agent configs from state)
- Fallback (conditional — visible only in fallback mode)
- Cross (conditional — visible only when cross-agents enabled)
- Remove

Remove: Agent name, Config folder, CLI Flags columns. The old `_COL_ID` column is also removed — `agent_id` is now generated internally from `config_id` (see step 3).

### 2. Update `_render_table()`
- Replace `_agent_cli_widget`, `_config_dir_widget`, `_cli_flags_widget` with a single `_config_id_widget` that shows a QComboBox.
- The QComboBox options come from `load_agent_configs()` loaded from state.

### 3. Update internal data
- `self._rows` still holds `AgentInstance` objects, but now they only have `agent_id` and `config_id`.
- When a user adds a config to the row, auto-generate `agent_id` from `config_id` (set `agent_id = config_id`). This ensures uniqueness since two rows in the same environment cannot share the same config_id.
- The `agent_id` column is removed from the table (the row's internal AgentInstance still has it for serialization and fallback/cross refs).

### 4. Remove related widget methods
- Remove `_agent_cli_widget()`, `_config_dir_widget()`, `_cli_flags_widget()` methods.
- Remove their helper callback methods.

### 5. Update column constants
- Update `_COL_*` constants to reflect new column layout.
- Update `setHorizontalHeaderLabels` to new labels.

### 6. Update add-agent flow in `_on_add_agent()`
- Instead of picking an agent CLI, let user pick a config ID from saved configs.
- Or keep the Add button but it now adds a row with a config ID selector.

### 7. Load agent configs for this tab
- Import `load_agent_configs` from `agents_runner.agent_configs.storage`.
- Call it to populate the config ID dropdowns.

## Success criteria
- Table shows simplified columns: Priority, Config ID, Fallback (conditional), Cross (conditional), Remove.
- Config ID dropdown contains entries from saved agent configs in state.toml.
- Adding/removing rows works.
- UI doesn't crash when no configs exist (show empty dropdown).

## Completion note
- Completed 2026-05-28: simplified the agents tab to config-id-driven rows, preserved fallback/pinned/cross behavior, and wired dropdowns to saved agent configs loaded from state.
