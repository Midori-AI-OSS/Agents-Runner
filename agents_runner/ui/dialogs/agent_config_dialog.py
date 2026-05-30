"""Agent config create/edit dialog."""

from __future__ import annotations

import os
import re
import shlex

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox
from PySide6.QtWidgets import QDialogButtonBox
from PySide6.QtWidgets import QFileDialog
from PySide6.QtWidgets import QFormLayout
from PySide6.QtWidgets import QHBoxLayout
from PySide6.QtWidgets import QLineEdit
from PySide6.QtWidgets import QMessageBox
from PySide6.QtWidgets import QToolButton
from PySide6.QtWidgets import QWidget

from agents_runner.agent_configs.model import AgentConfig
from agents_runner.agent_configs.storage import load_agent_configs
from agents_runner.agent_labels import format_agent_ui_label
from agents_runner.agent_systems.registry import available_agent_system_names
from agents_runner.agent_systems.status import command_in_path
from agents_runner.opencode_models import opencode_model_options_by_provider
from agents_runner.persistence import default_state_path
from agents_runner.ui.dialogs.themed_dialog import ThemedDialog


_CONFIG_ID_RE = re.compile(r"^[a-z0-9_-]{1,64}$")


class AgentConfigDialog(ThemedDialog):
    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        config: AgentConfig | None = None,
        initial_agent: str = "",
        initial_model: str = "",
        initial_variant: str = "",
    ) -> None:
        super().__init__(parent)
        self._editing = config is not None
        self._result: AgentConfig | None = None
        self._original_config_id = (
            str(getattr(config, "config_id", "") or "").strip().lower()
        )

        self.setWindowTitle("Edit Agent Config" if self._editing else "Agent Config")
        self.setMinimumWidth(520)

        layout = self.content_layout()

        self._model_variants: dict[str, list[str]] = {}
        self._models_by_provider: dict[str, list[tuple[str, str, list[str]]]] | None = (
            None
        )
        self._form = QFormLayout()
        self._form.setContentsMargins(0, 0, 0, 0)
        self._form.setHorizontalSpacing(12)
        self._form.setVerticalSpacing(10)
        layout.addLayout(self._form)

        self._config_id = QLineEdit()
        self._config_id.setMaxLength(64)
        self._config_id.setReadOnly(self._editing)
        self._form.addRow("Config ID", self._config_id)

        self._agent_cli = QComboBox()
        self._populate_agent_cli_combo()
        self._form.addRow("Agent CLI", self._agent_cli)

        self._config_dir = QLineEdit()
        config_dir_row = QWidget()
        config_dir_layout = QHBoxLayout(config_dir_row)
        config_dir_layout.setContentsMargins(0, 0, 0, 0)
        config_dir_layout.setSpacing(8)
        config_dir_layout.addWidget(self._config_dir, 1)
        self._browse = QToolButton()
        self._browse.setText("Browse")
        self._browse.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self._browse.clicked.connect(self._browse_config_dir)
        config_dir_layout.addWidget(self._browse)
        self._form.addRow("Config Dir", config_dir_row)

        self._cli_flags = QLineEdit()
        self._form.addRow("CLI Flags", self._cli_flags)

        self._agent_edit = QLineEdit()
        self._agent_edit.setMaxLength(128)
        self._form.addRow("Agent", self._agent_edit)

        self._provider_combo = QComboBox()
        self._form.addRow("Provider", self._provider_combo)

        self._model_combo = QComboBox()
        self._form.addRow("Model", self._model_combo)

        self._variant_combo = QComboBox()
        self._form.addRow("Variant", self._variant_combo)

        self._populate_provider_combo()
        self._set_form_row_visible(self._agent_edit, False)
        self._set_form_row_visible(self._provider_combo, False)
        self._set_form_row_visible(self._model_combo, False)
        self._set_form_row_visible(self._variant_combo, False)

        self._agent_cli.currentIndexChanged.connect(self._on_agent_cli_changed)
        self._provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        self._model_combo.currentIndexChanged.connect(self._on_model_changed)
        self._cli_flags.textChanged.connect(self._on_cli_flags_text_changed)
        self._on_model_changed(self._model_combo.currentIndex())
        self._on_agent_cli_changed(self._agent_cli.currentIndex())

        layout.addStretch(1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.Save
        )
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self._on_save)
        layout.addWidget(buttons)

        if config is not None:
            self._prefill(config)

        if not self._editing:
            if initial_agent:
                self._agent_edit.setText(initial_agent)
            if initial_model:
                provider, _, _ = initial_model.partition("/")
                if provider.strip():
                    self._set_provider_selection(provider.strip())
                self._set_model_selection(initial_model)
            if initial_variant:
                self._set_variant_selection(initial_variant)

    def agent_config(self) -> AgentConfig | None:
        return self._result

    def _prefill(self, config: AgentConfig) -> None:
        self._config_id.setText(str(config.config_id or "").strip())
        self._set_agent_cli(str(config.agent_cli or "").strip())
        self._config_dir.setText(str(config.config_dir or "").strip())
        self._cli_flags.setText(str(config.cli_flags or "").strip())
        self._agent_edit.setText(str(config.agent or "").strip())
        model_value = str(config.model or "").strip()
        if model_value:
            provider, _, _ = model_value.partition("/")
            if provider.strip():
                self._set_provider_selection(provider.strip())
        self._set_model_selection(model_value)
        self._set_variant_selection(str(config.variant or "").strip())

    def _populate_agent_cli_combo(self) -> None:
        self._agent_cli.clear()
        self._agent_cli.addItem("—", "")
        for agent_name in available_agent_system_names(include_internal=False):
            if not command_in_path(agent_name):
                continue
            label = format_agent_ui_label(agent_name)
            self._agent_cli.addItem(label, agent_name)

    def _populate_provider_combo(self) -> None:
        self._models_by_provider = opencode_model_options_by_provider()
        self._provider_combo.clear()
        self._provider_combo.addItem("—", "")
        for provider in sorted(self._models_by_provider, key=lambda p: p.casefold()):
            self._provider_combo.addItem(provider, provider)

    def _populate_model_combo_for_provider(self, provider: str) -> None:
        self._model_variants = {}
        was_blocked = self._model_combo.blockSignals(True)
        self._model_combo.clear()
        self._model_combo.addItem("—", "")
        models = (
            self._models_by_provider.get(provider, [])
            if self._models_by_provider is not None
            else []
        )
        for model_id, display_label, variants in models:
            normalized_model_id = str(model_id or "").strip()
            if not normalized_model_id:
                continue

            variant_names: list[str] = []
            seen_variants: set[str] = set()
            for raw_variant in variants:
                variant_name = str(raw_variant or "").strip()
                if not variant_name or variant_name in seen_variants:
                    continue
                seen_variants.add(variant_name)
                variant_names.append(variant_name)

            self._model_variants[normalized_model_id] = variant_names
            self._model_combo.addItem(
                self._format_model_label(normalized_model_id, str(display_label or "")),
                normalized_model_id,
            )
        self._model_combo.blockSignals(was_blocked)
        self._populate_variant_combo("")

    def _on_agent_cli_changed(self, _index: int) -> None:
        self._update_opencode_fields_visibility()
        if self._editing:
            return
        if str(self._config_id.text() or "").strip():
            return
        agent_cli = str(self._agent_cli.currentData() or "").strip()
        if not agent_cli:
            return
        self._config_id.setText(agent_cli)

    def _on_model_changed(self, _index: int) -> None:
        self._populate_variant_combo("")

    def _on_provider_changed(self, _index: int) -> None:
        provider = str(self._provider_combo.currentData() or "").strip()
        self._populate_model_combo_for_provider(provider)

    def _on_cli_flags_text_changed(self) -> None:
        text = str(self._cli_flags.text() or "").strip()
        if not text:
            return

        try:
            parts = shlex.split(text)
        except ValueError:
            return

        agent = ""
        model = ""
        variant = ""
        i = 0
        while i < len(parts):
            arg = parts[i]
            if arg in {"--agent", "--model", "--variant"} and i + 1 < len(parts):
                value = parts[i + 1]
                if not value.startswith("-"):
                    if arg == "--agent":
                        agent = value
                    elif arg == "--model":
                        model = value
                    else:
                        variant = value
                    i += 1
            i += 1

        if agent and not str(self._agent_edit.text() or "").strip():
            self._agent_edit.setText(agent)
        if model and not str(self._model_combo.currentData() or "").strip():
            provider, _, _ = model.partition("/")
            if provider.strip():
                self._set_provider_selection(provider.strip())
            self._set_model_selection(model)
        if variant and not str(self._variant_combo.currentData() or "").strip():
            self._set_variant_selection(variant)

    def _set_agent_cli(self, value: str) -> None:
        normalized = str(value or "").strip().lower()
        for i in range(self._agent_cli.count()):
            if str(self._agent_cli.itemData(i) or "") == normalized:
                self._agent_cli.setCurrentIndex(i)
                return

        if normalized:
            self._agent_cli.addItem(format_agent_ui_label(normalized), normalized)
            self._agent_cli.setCurrentIndex(self._agent_cli.count() - 1)
        else:
            self._agent_cli.setCurrentIndex(0)

    def _set_model_selection(self, value: str) -> None:
        normalized = str(value or "").strip()
        if normalized and self._combo_index_for_data(self._model_combo, normalized) < 0:
            self._model_variants.setdefault(normalized, [])
            self._model_combo.addItem(
                self._format_model_label(normalized, ""), normalized
            )
        self._set_combo_current_data(self._model_combo, normalized)

    def _set_variant_selection(self, value: str) -> None:
        normalized = str(value or "").strip()
        if (
            normalized
            and self._combo_index_for_data(self._variant_combo, normalized) < 0
        ):
            self._variant_combo.addItem(normalized, normalized)
        self._set_combo_current_data(self._variant_combo, normalized)

    def _set_provider_selection(self, value: str) -> None:
        self._set_combo_current_data(self._provider_combo, str(value or "").strip())

    def _populate_variant_combo(self, selected_variant: str) -> None:
        model_id = str(self._model_combo.currentData() or "").strip()
        was_blocked = self._variant_combo.blockSignals(True)
        self._variant_combo.clear()
        self._variant_combo.addItem("None", "")
        for variant_name in self._model_variants.get(model_id, []):
            self._variant_combo.addItem(variant_name, variant_name)

        normalized_variant = str(selected_variant or "").strip()
        if (
            normalized_variant
            and self._combo_index_for_data(self._variant_combo, normalized_variant) < 0
        ):
            self._variant_combo.addItem(normalized_variant, normalized_variant)
        self._variant_combo.blockSignals(was_blocked)
        self._set_combo_current_data(self._variant_combo, normalized_variant)

    def _update_opencode_fields_visibility(self) -> None:
        is_opencode = (
            str(self._agent_cli.currentData() or "").strip().lower() == "opencode"
        )
        self._set_form_row_visible(self._agent_edit, is_opencode)
        self._set_form_row_visible(self._provider_combo, is_opencode)
        self._set_form_row_visible(self._model_combo, is_opencode)
        self._set_form_row_visible(self._variant_combo, is_opencode)

    def _set_form_row_visible(self, field: QWidget, visible: bool) -> None:
        label = self._form.labelForField(field)
        label.setVisible(visible)
        field.setVisible(visible)

    def _combo_index_for_data(self, combo: QComboBox, value: str) -> int:
        normalized = str(value or "").strip()
        for i in range(combo.count()):
            if str(combo.itemData(i) or "").strip() == normalized:
                return i
        return -1

    def _set_combo_current_data(self, combo: QComboBox, value: str) -> None:
        index = self._combo_index_for_data(combo, value)
        if index >= 0:
            combo.setCurrentIndex(index)
            return
        if combo.count() > 0:
            combo.setCurrentIndex(0)

    def _format_model_label(self, model_id: str, display_label: str) -> str:
        label = str(display_label or "").strip()
        if label:
            return label
        return str(model_id or "").strip()

    def _browse_config_dir(self) -> None:
        current = str(self._config_dir.text() or "").strip()
        start_dir = current or os.path.expanduser("~")
        path = QFileDialog.getExistingDirectory(self, "Select Config Folder", start_dir)
        if path:
            self._config_dir.setText(path)

    def _on_save(self) -> None:
        config_id = str(self._config_id.text() or "").strip()
        if not config_id:
            QMessageBox.warning(self, "Invalid config", "Config ID is required.")
            self._config_id.setFocus()
            return
        if not _CONFIG_ID_RE.fullmatch(config_id):
            QMessageBox.warning(self, "Invalid config", "Config ID is invalid.")
            self._config_id.setFocus()
            return

        if not self._editing and self._config_id_exists(config_id):
            QMessageBox.warning(self, "Invalid config", "Config ID already exists.")
            self._config_id.setFocus()
            return

        agent_cli = str(self._agent_cli.currentData() or "").strip().lower()
        if not agent_cli:
            QMessageBox.warning(self, "Invalid config", "Agent CLI is required.")
            self._agent_cli.setFocus()
            return

        config_dir = os.path.expanduser(str(self._config_dir.text() or "").strip())
        cli_flags = str(self._cli_flags.text() or "").strip()
        agent = str(self._agent_edit.text() or "").strip()
        model = str(self._model_combo.currentData() or "").strip()
        variant = str(self._variant_combo.currentData() or "").strip()

        self._result = AgentConfig(
            config_id=config_id,
            agent_cli=agent_cli,
            config_dir=config_dir,
            cli_flags=cli_flags,
            agent=agent,
            model=model,
            variant=variant,
        )
        self.accept()

    def _config_id_exists(self, config_id: str) -> bool:
        target = str(config_id or "").strip().lower()
        if not target:
            return False
        try:
            configs = load_agent_configs(default_state_path())
        except Exception:
            configs = []
        for cfg in configs:
            existing = str(getattr(cfg, "config_id", "") or "").strip().lower()
            if existing and existing == target and existing != self._original_config_id:
                return True
        return False
