# Add "Agent Configs" Pane to Settings Page

## Files to modify
- `agents_runner/ui/pages/settings_form.py`

## Actions

### 1. Add pane spec to `_default_pane_specs()`
- Add a new `_SettingsPaneSpec` entry:
  ```python
  _SettingsPaneSpec(
      key="agent_configs",
      title="Agent Configs",
      subtitle="Named agent configurations shared across environments.",
      section="Agent Setup",
  )
  ```

### 2. Add controls in `_build_controls()`
- Add a `QTableWidget` or `QListWidget` to display saved agent configs (columns: Config ID, Agent CLI, Config Dir, CLI Flags).
- Add Add / Edit / Delete `QToolButton`s.
- Wire up button handlers:
  - **Add**: Open `AgentConfigDialog` in create mode, save to state on accept.
  - **Edit**: Open `AgentConfigDialog` with selected config, save to state on accept.
  - **Delete**: Confirm via `QMessageBox.warning`. Before deleting, check if any environments reference the config using `find_envs_referencing_config()`. If yes, show warning listing the env names and ask for confirmation.

### 3. Add pane page in `_build_pages()`
- Create a page using `_create_page(specs_by_key["agent_configs"])`.
- Build the table and buttons in the body layout.
- Call `self._register_page("agent_configs", page)`.

### 4. Load agent configs
- In the method that loads settings data, call `load_agent_configs()` from `agent_configs.storage` and populate the table.
- Use `self._state_path` (set from `default_state_path()` on MainWindow init) — same path the rest of the settings page uses.

### 5. Save agent configs
- On table change (add/edit/delete), call `save_agent_config()` or `delete_agent_config()` to persist immediately.

## Success criteria
- Settings page shows new "Agent Configs" nav item under "Agent Setup" section.
- Table shows saved configs, Add opens dialog, Edit pre-fills dialog, Delete confirms and removes.
- Delete with referenced envs shows warning listing those envs.
