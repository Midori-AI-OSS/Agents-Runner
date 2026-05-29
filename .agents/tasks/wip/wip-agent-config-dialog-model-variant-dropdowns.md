# Task: Add agent/model/variant fields to AgentConfigDialog for OpenCode

**File:** `agents_runner/ui/dialogs/agent_config_dialog.py`

**Depends on:** `wip-opencode-models-parser.md`, `wip-model-variant-agentconfig-dataclass.md`

**Goal:** When "opencode" is selected as the Agent CLI in the AgentConfigDialog, show three additional fields: a freeform text input for agent name, a dropdown for model, and a dropdown for reasoning-effort variant. Populate model/variant from the opencode models parser.

**Background:**
Currently the dialog has: Config ID (QLineEdit), Agent CLI (QComboBox), Config Dir (QLineEdit + Browse), CLI Flags (QLineEdit). The agent name, model, and variant need to be first-class selections for opencode rather than typed manually into CLI Flags. The `--agent` flag is supported by both `opencode` TUI (`opencode --agent worker`) and `opencode run` (`opencode run --agent worker`).

**Steps:**
1. Import `opencode_model_options` from `agents_runner.opencode_models`.
2. Add a `self._agent_edit = QLineEdit()` widget for the agent name (freeform text, not a dropdown). Users type their agent name (e.g., `"worker"`). Set a reasonable max length (e.g., `setMaxLength(128)`).
3. Add a `self._model_combo = QComboBox()` widget.
4. Add a `self._variant_combo = QComboBox()` widget.
5. Add all three to the form after the CLI Flags row, initially hidden (`setVisible(False)`). Order: Agent, Model, Variant. Form labels: `"Agent"`, `"Model"`, `"Variant"`.
6. Populate `self._model_combo` with data from `opencode_model_options()`: display format like `"deepseek-v4-flash-free (OpenCode)"`, store full model ID as user data.
7. Connect `self._model_combo.currentIndexChanged` to a handler that repopulates `self._variant_combo` with variants for the selected model. The variant combo should include a "None" option (empty string) for no variant.
8. Connect `self._agent_cli.currentIndexChanged` to show/hide the agent/model/variant rows: visible only when the selected agent CLI is `"opencode"`.
9. In `_prefill()`: when editing an existing config, set `self._agent_edit.setText(...)` with the config's `agent` field. Also select matching items in the model/variant combos (or add them if not in the list).
10. In `_on_save()`: set `agent = str(self._agent_edit.text() or "").strip()`, `model = str(self._model_combo.currentData() or "").strip()`, and `variant = str(self._variant_combo.currentData() or "").strip()` in the resulting `AgentConfig`.
11. Do NOT automatically update `cli_flags` text from these fields — keep agent/model/variant as separate fields.

**Done criteria:**
- When "OpenCode" is selected as Agent CLI, agent (QLineEdit), model (QComboBox), and variant (QComboBox) fields appear.
- Agent field accepts freeform text input (not a dropdown).
- Model dropdown is populated from `opencode models --verbose` output.
- Selecting a model repopulates the variant dropdown with that model's available variants.
- Saving the dialog stores the entered agent and selected model/variant in `AgentConfig.agent`, `AgentConfig.model`, and `AgentConfig.variant`.
- Re-opening an existing opencode config pre-fills all three fields correctly.
- For non-opencode agent CLIs, the three fields are hidden.
