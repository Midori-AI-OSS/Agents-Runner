# Create `AgentConfigDialog` Popup

## Files to create
- `agents_runner/ui/dialogs/agent_config_dialog.py`

## Actions

### 1. Create `AgentConfigDialog` class
- Subclass `ThemedDialog` (from `agents_runner/ui/dialogs/themed_dialog.py`).
- Follow patterns from existing dialogs like `TestChainDialog` or `FirstRunSetupDialog`.
- Constructor: `__init__(self, parent=None, *, config=None)` where `config` is an optional `AgentConfig` for edit mode.

### 2. Form fields
- **Config ID** (`QLineEdit`): Read-only if editing, editable if creating new.
  - Validate: lowercase, alphanumeric + `-` + `_`, max 64 chars.
- **Agent CLI** (`QComboBox`): Populated from `available_agent_system_names(include_internal=False)` using `format_agent_ui_label`.
- **Config Dir** (`QLineEdit` + "Browse" `QToolButton`): Opens `QFileDialog.getExistingDirectory` for host directory selection.
- **CLI Flags** (`QLineEdit`): Free-text CLI flags string.

### 3. Buttons
- Use `QDialogButtonBox` with Save and Cancel.
- Save validates:
  - `config_id` is not empty.
  - `config_id` is unique (if creating new).
  - `agent_cli` is selected.
- On save: emit a signal or return the `AgentConfig` via a property.

### 4. Public API
- `agent_config() -> AgentConfig | None`: Returns the built config, or None if canceled.
- Or use `exec()` pattern returning `QDialog.Accepted`/`QDialog.Rejected`.

### 5. Style
- Minimal — no verbose help text, just field labels + buttons.
- Window title: "Agent Config" or "Edit Agent Config" depending on mode.

## Success criteria
- Dialog opens from code, fields populate, Save returns valid AgentConfig, Cancel returns None.
- Config Dir Browse button opens native directory picker.
