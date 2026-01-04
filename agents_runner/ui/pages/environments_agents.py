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
from PySide6.QtWidgets import QToolButton
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
            "Agents are used in priority order (top to bottom). Use arrows to reorder."
        )
        header_label.setStyleSheet("color: rgba(237, 239, 245, 160);")
        layout.addWidget(header_label)

        table_label = QLabel("Select and order agents:")
        layout.addWidget(table_label)

        self._agent_table = QTableWidget()
        self._agent_table.setColumnCount(4)
        self._agent_table.setHorizontalHeaderLabels(["Enabled", "Agent", "Priority", "Fallback"])
        self._agent_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._agent_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._agent_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._agent_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self._agent_table.verticalHeader().setVisible(False)
        self._agent_table.setSelectionMode(QTableWidget.NoSelection)
        self._agent_table.setRowCount(len(SUPPORTED_AGENTS))

        self._agent_checkboxes: dict[str, QCheckBox] = {}
        self._agent_up_buttons: dict[str, QToolButton] = {}
        self._agent_down_buttons: dict[str, QToolButton] = {}
        self._agent_fallback_combos: dict[str, QComboBox] = {}

        for i, agent in enumerate(SUPPORTED_AGENTS):
            # Checkbox for enabling/disabling
            checkbox = QCheckBox()
            checkbox.toggled.connect(self._on_agent_selection_changed)
            self._agent_checkboxes[agent] = checkbox

            checkbox_widget = QWidget()
            checkbox_layout = QHBoxLayout(checkbox_widget)
            checkbox_layout.setContentsMargins(10, 0, 0, 0)
            checkbox_layout.addWidget(checkbox)
            checkbox_layout.addStretch(1)

            self._agent_table.setCellWidget(i, 0, checkbox_widget)
            
            # Agent name
            self._agent_table.setItem(i, 1, QTableWidgetItem(agent.title()))

            # Priority controls (up/down arrows)
            priority_widget = QWidget()
            priority_layout = QHBoxLayout(priority_widget)
            priority_layout.setContentsMargins(4, 2, 4, 2)
            priority_layout.setSpacing(4)

            up_btn = QToolButton()
            up_btn.setText("↑")
            up_btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
            up_btn.clicked.connect(lambda checked, a=agent: self._move_agent_up(a))
            self._agent_up_buttons[agent] = up_btn

            down_btn = QToolButton()
            down_btn.setText("↓")
            down_btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
            down_btn.clicked.connect(lambda checked, a=agent: self._move_agent_down(a))
            self._agent_down_buttons[agent] = down_btn

            priority_layout.addWidget(up_btn)
            priority_layout.addWidget(down_btn)
            priority_layout.addStretch(1)

            self._agent_table.setCellWidget(i, 2, priority_widget)

            # Fallback dropdown
            fallback_combo = QComboBox()
            fallback_combo.addItem("—", "")
            fallback_combo.currentIndexChanged.connect(lambda _idx: self.agents_changed.emit())
            self._agent_fallback_combos[agent] = fallback_combo

            self._agent_table.setCellWidget(i, 3, fallback_combo)

        layout.addWidget(self._agent_table)

        self._selection_mode_label = QLabel("Selection mode (when multiple agents enabled):")
        layout.addWidget(self._selection_mode_label)

        mode_row = QHBoxLayout()
        mode_row.setSpacing(10)
        self._selection_mode = QComboBox()
        self._selection_mode.addItem("Round-robin", "round-robin")
        self._selection_mode.addItem("Least recently used", "least-used")
        self._selection_mode.addItem("Fallback (use next on failure)", "fallback")
        self._selection_mode.setMaximumWidth(300)
        self._selection_mode.currentIndexChanged.connect(self._on_selection_mode_changed)
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

        self._refresh_fallback_visibility()

    def _on_agent_selection_changed(self) -> None:
        self._refresh_fallback_visibility()
        self._update_fallback_options()
        self.agents_changed.emit()

    def _on_selection_mode_changed(self, _index: int) -> None:
        self._refresh_fallback_visibility()
        self.agents_changed.emit()

    def _refresh_fallback_visibility(self) -> None:
        """Show/hide fallback column based on selection mode."""
        selection_mode = str(self._selection_mode.currentData() or "round-robin")
        is_fallback_mode = selection_mode == "fallback"
        
        # Show/hide the Fallback column
        self._agent_table.setColumnHidden(3, not is_fallback_mode)

    def _update_fallback_options(self) -> None:
        """Update fallback dropdown options to include only enabled agents."""
        enabled = self._get_enabled_agents_ordered()
        
        for agent, combo in self._agent_fallback_combos.items():
            current_value = combo.currentData()
            combo.blockSignals(True)
            combo.clear()
            combo.addItem("—", "")
            
            # Add other enabled agents as fallback options (excluding self)
            for other_agent in enabled:
                if other_agent != agent:
                    combo.addItem(other_agent.title(), other_agent)
            
            # Restore previous selection if still valid
            if current_value:
                idx = combo.findData(current_value)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
            
            combo.blockSignals(False)

    def _get_enabled_agents_ordered(self) -> list[str]:
        """Get list of enabled agents in current table order."""
        enabled = []
        for i in range(self._agent_table.rowCount()):
            agent_item = self._agent_table.item(i, 1)
            if agent_item:
                agent_name = agent_item.text().lower()
                if agent_name in self._agent_checkboxes:
                    if self._agent_checkboxes[agent_name].isChecked():
                        enabled.append(agent_name)
        return enabled

    def _move_agent_up(self, agent: str) -> None:
        """Move agent up in priority (swap with row above)."""
        current_row = self._find_agent_row(agent)
        if current_row <= 0:
            return
        
        self._swap_rows(current_row, current_row - 1)
        self._update_fallback_options()
        self.agents_changed.emit()

    def _move_agent_down(self, agent: str) -> None:
        """Move agent down in priority (swap with row below)."""
        current_row = self._find_agent_row(agent)
        if current_row < 0 or current_row >= self._agent_table.rowCount() - 1:
            return
        
        self._swap_rows(current_row, current_row + 1)
        self._update_fallback_options()
        self.agents_changed.emit()

    def _find_agent_row(self, agent: str) -> int:
        """Find the current row index for an agent."""
        for i in range(self._agent_table.rowCount()):
            item = self._agent_table.item(i, 1)
            if item and item.text().lower() == agent.lower():
                return i
        return -1

    def _swap_rows(self, row1: int, row2: int) -> None:
        """Swap two rows in the table."""
        if row1 < 0 or row2 < 0 or row1 >= self._agent_table.rowCount() or row2 >= self._agent_table.rowCount():
            return
        
        # Get agent names from both rows
        item1 = self._agent_table.item(row1, 1)
        item2 = self._agent_table.item(row2, 1)
        if not item1 or not item2:
            return
        
        agent1 = item1.text().lower()
        agent2 = item2.text().lower()

        # Swap the item text
        item1.setText(agent2.title())
        item2.setText(agent1.title())

        # Update internal mapping references
        # The widgets are still correctly mapped by agent name in the dicts

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
            # Clear everything
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
            
            for combo in self._agent_fallback_combos.values():
                combo.blockSignals(True)
                combo.setCurrentIndex(0)
                combo.blockSignals(False)
        else:
            # Reorder table to match enabled_agents order
            self._reorder_table_by_list(agent_selection.enabled_agents)
            
            # Set checkboxes
            for agent, checkbox in self._agent_checkboxes.items():
                checkbox.blockSignals(True)
                checkbox.setChecked(agent in agent_selection.enabled_agents)
                checkbox.blockSignals(False)

            # Set selection mode
            idx = self._selection_mode.findData(agent_selection.selection_mode or "round-robin")
            self._selection_mode.blockSignals(True)
            if idx >= 0:
                self._selection_mode.setCurrentIndex(idx)
            else:
                self._selection_mode.setCurrentIndex(0)
            self._selection_mode.blockSignals(False)

            # Set config directories
            for agent, (label, line_edit, browse_btn) in self._agent_config_dir_widgets.items():
                line_edit.blockSignals(True)
                line_edit.setText(agent_selection.agent_config_dirs.get(agent, ""))
                line_edit.blockSignals(False)
            
            # Update fallback options first
            self._update_fallback_options()
            
            # Set fallback selections
            for agent, combo in self._agent_fallback_combos.items():
                fallback = agent_selection.agent_fallbacks.get(agent, "")
                combo.blockSignals(True)
                idx = combo.findData(fallback)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
                else:
                    combo.setCurrentIndex(0)
                combo.blockSignals(False)

        self._refresh_fallback_visibility()

    def _reorder_table_by_list(self, ordered_agents: list[str]) -> None:
        """Reorder table rows to match the given agent order."""
        # Build a map of where each agent should go
        target_positions = {agent: i for i, agent in enumerate(ordered_agents)}
        
        # Get remaining agents not in the list
        all_agents = list(SUPPORTED_AGENTS)
        remaining = [a for a in all_agents if a not in ordered_agents]
        
        # Complete the ordering: specified agents first, then remaining in original order
        full_order = ordered_agents + remaining
        
        # Update table items to reflect this order
        for i, agent in enumerate(full_order):
            item = self._agent_table.item(i, 1)
            if item:
                item.setText(agent.title())

    def get_agent_selection(self) -> AgentSelection | None:
        enabled_agents = self._get_enabled_agents_ordered()
        
        if not enabled_agents:
            return None

        selection_mode = str(self._selection_mode.currentData() or "round-robin")

        agent_config_dirs = {}
        for agent, (label, line_edit, browse_btn) in self._agent_config_dir_widgets.items():
            config_dir = os.path.expanduser(line_edit.text().strip())
            if config_dir:
                agent_config_dirs[agent] = config_dir

        agent_fallbacks = {}
        for agent, combo in self._agent_fallback_combos.items():
            fallback = str(combo.currentData() or "").strip()
            if fallback:
                agent_fallbacks[agent] = fallback

        return AgentSelection(
            enabled_agents=enabled_agents,
            selection_mode=selection_mode,
            agent_config_dirs=agent_config_dirs,
            agent_fallbacks=agent_fallbacks
        )
