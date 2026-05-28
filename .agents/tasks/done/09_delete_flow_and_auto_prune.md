# Delete Flow: Warn + Auto-Prune on Save

## Files to modify
- `agents_runner/environments/serialize.py`
- `agents_runner/ui/pages/settings_form.py`

## Actions

### 1. Delete handler with dependency warning
In `settings_form.py` (agent configs pane, from Task 6):

- When user clicks Delete on an agent config:
  1. Call `find_envs_referencing_config(state_path, config_id)`.
  2. If result is non-empty, show `QMessageBox.warning` listing:
     - "This config is referenced by X environment(s): env1, env2, env3"
     - "Deleting it will remove this config ID from those environments."
     - OK / Cancel buttons.
  3. If confirmed (or no references), call `delete_agent_config()`.
  4. Refresh the table.

### 2. Auto-prune on environment save
In `environments/serialize.py`:

- Add a function `prune_missing_config_ids(env: Environment, valid_config_ids: set[str]) -> Environment`:
  - For each agent in `env.agent_selection.agents`, if `agent.config_id` is non-empty and not in `valid_config_ids`, remove that agent. (Agents with empty `config_id` are kept — they use default config.)
  - Remove entries from `env.agent_selection.agent_fallbacks` where key or value references a removed agent_id.
  - If `env.agent_selection.pinned_agent_id` references a removed agent_id, set to empty string.
  - Remove entries from `env.cross_agent_allowlist` that reference removed agent_ids.
  - If `env.agent_selection.agents` becomes empty after pruning, set `env.agent_selection = None`.
  - The function is pure: it takes `valid_config_ids` as input (the caller is responsible for loading them from state).

### 3. Integration point
- Call `prune_missing_config_ids()` in `persistence.py`'s `save_state()` before writing environments to disk.
- In `save_state()`, load config IDs via `load_agent_configs(state_path)`, build a set of valid IDs, then prune each environment in the payload before serializing.
- Also call `prune_missing_config_ids()` in any UI save path that writes environments directly (search for `save_state` calls in main_window_environment.py and related files).

## Success criteria
- Deleting a config that is referenced by environments shows a warning dialog listing those environments.
- After confirmed delete, the config is removed from state.toml.
- On next environment save, environments that referenced the deleted config have those agents auto-pruned.
- Fallbacks, pinned_agent_id, and cross_agent_allowlist are all cleaned of dangling references.

## Completion
- Implemented live environment reference warnings and save-time pruning of deleted agent config references.
