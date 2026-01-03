from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QCheckBox
from PySide6.QtWidgets import QComboBox
from PySide6.QtWidgets import QFileDialog
from PySide6.QtWidgets import QGridLayout
from PySide6.QtWidgets import QHBoxLayout
from PySide6.QtWidgets import QHeaderView
from PySide6.QtWidgets import QLabel
from PySide6.QtWidgets import QLineEdit
from PySide6.QtWidgets import QPushButton
from PySide6.QtWidgets import QTableWidget
from PySide6.QtWidgets import QTableWidgetItem
from PySide6.QtWidgets import QVBoxLayout
from PySide6.QtWidgets import QWidget

from agents_runner.agent_cli import SUPPORTED_AGENTS
from agents_runner.environments.model import AgentSelection


class AgentsTabWidget(QWidget):
    agents_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._agent_config_dir_widgets: dict[str, tuple[QLabel, QLineEdit, QPushButton]] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 16, 0, 12)
        layout.setSpacing(10)

        header_label = QLabel(
            "Override the Settings agent configuration for this environment.\n"
            "You can select multiple agents and choose how they are used."
        )
        header_label.setStyleSheet("color: rgba(237, 239, 245, 160);")
        layout.addWidget(header_label)

        table_label = QLabel("Select agents to enable:")
        layout.addWidget(table_label)

        self._agent_table = QTableWidget()
        self._agent_table.setColumnCount(2)
        self._agent_table.setHorizontalHeaderLabels(["Enabled", "Agent"])
        self._agent_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._agent_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._agent_table.verticalHeader().setVisible(False)
        self._agent_table.setSelectionMode(QTableWidget.NoSelection)
        self._agent_table.setRowCount(len(SUPPORTED_AGENTS))

        self._agent_checkboxes: dict[str, QCheckBox] = {}

        for i, agent in enumerate(SUPPORTED_AGENTS):
            checkbox = QCheckBox()
            checkbox.toggled.connect(self._on_agent_selection_changed)
            self._agent_checkboxes[agent] = checkbox

            checkbox_widget = QWidget()
            checkbox_layout = QHBoxLayout(checkbox_widget)
            checkbox_layout.setContentsMargins(10, 0, 0, 0)
            checkbox_layout.addWidget(checkbox)
            checkbox_layout.addStretch(1)

            self._agent_table.setCellWidget(i, 0, checkbox_widget)
            self._agent_table.setItem(i, 1, QTableWidgetItem(agent.title()))

        layout.addWidget(self._agent_table)

        self._selection_mode_label = QLabel("Selection mode (when multiple agents enabled):")
        self._selection_mode_label.setVisible(False)
        layout.addWidget(self._selection_mode_label)

        mode_row = QHBoxLayout()
        mode_row.setSpacing(10)
        self._selection_mode = QComboBox()
        self._selection_mode.addItem("Round-robin", "round-robin")
        self._selection_mode.addItem("Least recently used", "least-used")
        self._selection_mode.addItem("Fallback (use next on failure)", "fallback")
        self._selection_mode.setMaximumWidth(300)
        self._selection_mode.setVisible(False)
        self._selection_mode.currentIndexChanged.connect(lambda _index: self.agents_changed.emit())
        mode_row.addWidget(self._selection_mode)
        mode_row.addStretch(1)
        layout.addLayout(mode_row)

        config_label = QLabel("Agent configuration directories:")
        layout.addWidget(config_label)

        config_grid = QGridLayout()
        config_grid.setHorizontalSpacing(10)
        config_grid.setVerticalSpacing(10)
        config_grid.setColumnStretch(1, 1)

        row = 0
        for agent in SUPPORTED_AGENTS:
            label = QLabel(f"{agent.title()} config:")
            line_edit = QLineEdit()
            line_edit.setPlaceholderText(f"~/.{agent}")
            line_edit.textChanged.connect(lambda _text: self.agents_changed.emit())

            browse_btn = QPushButton("Browse…")
            browse_btn.setFixedWidth(100)
            browse_btn.clicked.connect(lambda checked, a=agent: self._browse_config_dir(a))

            config_grid.addWidget(label, row, 0)
            config_grid.addWidget(line_edit, row, 1)
            config_grid.addWidget(browse_btn, row, 2)

            self._agent_config_dir_widgets[agent] = (label, line_edit, browse_btn)
            row += 1

        layout.addLayout(config_grid)
        layout.addStretch(1)

    def _on_agent_selection_changed(self) -> None:
        enabled_count = sum(1 for cb in self._agent_checkboxes.values() if cb.isChecked())
        multi_agent_mode = enabled_count > 1

        self._selection_mode_label.setVisible(multi_agent_mode)
        self._selection_mode.setVisible(multi_agent_mode)

        self.agents_changed.emit()

    def _browse_config_dir(self, agent: str) -> None:
        if agent not in self._agent_config_dir_widgets:
            return

        label, line_edit, browse_btn = self._agent_config_dir_widgets[agent]
        current = line_edit.text() or os.path.expanduser(f"~/.{agent}")

        path = QFileDialog.getExistingDirectory(
            self,
            f"Select {agent.title()} Config folder",
            current,
        )
        if path:
            line_edit.setText(path)

    def set_agent_selection(self, agent_selection: AgentSelection | None) -> None:
        if agent_selection is None:
            for checkbox in self._agent_checkboxes.values():
                checkbox.blockSignals(True)
                checkbox.setChecked(False)
                checkbox.blockSignals(False)

            self._selection_mode.blockSignals(True)
            self._selection_mode.setCurrentIndex(0)
            self._selection_mode.blockSignals(False)

            for agent, (label, line_edit, browse_btn) in self._agent_config_dir_widgets.items():
                line_edit.blockSignals(True)
                line_edit.setText("")
                line_edit.blockSignals(False)
        else:
            for agent, checkbox in self._agent_checkboxes.items():
                checkbox.blockSignals(True)
                checkbox.setChecked(agent in agent_selection.enabled_agents)
                checkbox.blockSignals(False)

            idx = self._selection_mode.findData(agent_selection.selection_mode or "round-robin")
            self._selection_mode.blockSignals(True)
            if idx >= 0:
                self._selection_mode.setCurrentIndex(idx)
            else:
                self._selection_mode.setCurrentIndex(0)
            self._selection_mode.blockSignals(False)

            for agent, (label, line_edit, browse_btn) in self._agent_config_dir_widgets.items():
                line_edit.blockSignals(True)
                line_edit.setText(agent_selection.agent_config_dirs.get(agent, ""))
                line_edit.blockSignals(False)

        self._on_agent_selection_changed()

    def get_agent_selection(self) -> AgentSelection | None:
        enabled_agents = [agent for agent, cb in self._agent_checkboxes.items() if cb.isChecked()]
        
        if not enabled_agents:
            return None

        selection_mode = str(self._selection_mode.currentData() or "round-robin")

        agent_config_dirs = {}
        for agent, (label, line_edit, browse_btn) in self._agent_config_dir_widgets.items():
            config_dir = os.path.expanduser(line_edit.text().strip())
            if config_dir:
                agent_config_dirs[agent] = config_dir

        return AgentSelection(
            enabled_agents=enabled_agents,
            selection_mode=selection_mode,
            agent_config_dirs=agent_config_dirs
        )
