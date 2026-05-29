"""Agent config create/edit dialog."""

from __future__ import annotations

import os
import re

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
from agents_runner.persistence import default_state_path
from agents_runner.ui.dialogs.themed_dialog import ThemedDialog


_CONFIG_ID_RE = re.compile(r"^[a-z0-9_-]{1,64}$")


class AgentConfigDialog(ThemedDialog):
    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        config: AgentConfig | None = None,
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

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)
        layout.addLayout(form)

        self._config_id = QLineEdit()
        self._config_id.setMaxLength(64)
        self._config_id.setReadOnly(self._editing)
        form.addRow("Config ID", self._config_id)

        self._agent_cli = QComboBox()
        self._populate_agent_cli_combo()
        form.addRow("Agent CLI", self._agent_cli)

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
        form.addRow("Config Dir", config_dir_row)

        self._cli_flags = QLineEdit()
        form.addRow("CLI Flags", self._cli_flags)

        self._agent_cli.currentIndexChanged.connect(self._on_agent_cli_changed)

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

    def agent_config(self) -> AgentConfig | None:
        return self._result

    def _prefill(self, config: AgentConfig) -> None:
        self._config_id.setText(str(config.config_id or "").strip())
        self._set_agent_cli(str(config.agent_cli or "").strip())
        self._config_dir.setText(str(config.config_dir or "").strip())
        self._cli_flags.setText(str(config.cli_flags or "").strip())

    def _populate_agent_cli_combo(self) -> None:
        self._agent_cli.clear()
        self._agent_cli.addItem("—", "")
        for agent_name in available_agent_system_names(include_internal=False):
            if not command_in_path(agent_name):
                continue
            label = format_agent_ui_label(agent_name)
            self._agent_cli.addItem(label, agent_name)

    def _on_agent_cli_changed(self, _index: int) -> None:
        if self._editing:
            return
        if str(self._config_id.text() or "").strip():
            return
        agent_cli = str(self._agent_cli.currentData() or "").strip()
        if not agent_cli:
            return
        self._config_id.setText(agent_cli)

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

        self._result = AgentConfig(
            config_id=config_id,
            agent_cli=agent_cli,
            config_dir=config_dir,
            cli_flags=cli_flags,
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
