from __future__ import annotations

import os
from uuid import uuid4

from PySide6.QtCore import Qt
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox
from PySide6.QtWidgets import QFileDialog
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
from agents_runner.environments.model import AgentInstance
from agents_runner.environments.model import AgentSelection


class AgentsTabWidget(QWidget):
    agents_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 16, 0, 12)
        layout.setSpacing(10)

        header_label = QLabel(
            "Configure agents for this environment.\n"
            "Each agent instance can have its own config directory. "
            "Agents are used in priority order (top to bottom)."
        )
        header_label.setStyleSheet("color: rgba(237, 239, 245, 160);")
        layout.addWidget(header_label)

        # Add agent button row
        add_row = QHBoxLayout()
        add_row.setSpacing(10)
        
        add_label = QLabel("Add agent:")
        add_row.addWidget(add_label)
        
        self._agent_type_combo = QComboBox()
        for agent in SUPPORTED_AGENTS:
            self._agent_type_combo.addItem(agent.title(), agent)
        self._agent_type_combo.setMaximumWidth(150)
        add_row.addWidget(self._agent_type_combo)
        
        self._add_agent_btn = QPushButton("Add Agent")
        self._add_agent_btn.setFixedWidth(100)
        self._add_agent_btn.clicked.connect(self._on_add_agent)
        add_row.addWidget(self._add_agent_btn)
        
        add_row.addStretch(1)
        layout.addLayout(add_row)

        # Agent instances table
        table_label = QLabel("Agent instances:")
        layout.addWidget(table_label)

        self._agent_table = QTableWidget()
        self._agent_table.setColumnCount(6)
        self._agent_table.setHorizontalHeaderLabels([
            "Agent Type", "Config Directory", "Priority", "Fallback", "Actions", ""
        ])
        
        # Set column resize modes
        self._agent_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._agent_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._agent_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._agent_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self._agent_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self._agent_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Fixed)
        
        self._agent_table.verticalHeader().setVisible(False)
        self._agent_table.setSelectionMode(QTableWidget.NoSelection)
        self._agent_table.setRowCount(0)
        
        # Make table items non-editable
        self._agent_table.setEditTriggers(QTableWidget.NoEditTriggers)

        layout.addWidget(self._agent_table)

        # Selection mode
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

        layout.addStretch(1)

        self._refresh_fallback_visibility()

    def _on_add_agent(self) -> None:
        """Add a new agent instance to the table."""
        agent_type = str(self._agent_type_combo.currentData() or "codex")
        instance_id = f"agent-{uuid4().hex[:8]}"
        
        # Add new row
        row = self._agent_table.rowCount()
        self._agent_table.insertRow(row)
        
        # Set agent type (non-editable)
        type_item = QTableWidgetItem(agent_type.title())
        type_item.setFlags(type_item.flags() & ~Qt.ItemIsEditable)
        type_item.setData(Qt.UserRole, instance_id)  # Store instance_id
        type_item.setData(Qt.UserRole + 1, agent_type)  # Store agent_type
        self._agent_table.setItem(row, 0, type_item)
        
        # Config directory with browse button
        config_widget = QWidget()
        config_layout = QHBoxLayout(config_widget)
        config_layout.setContentsMargins(4, 2, 4, 2)
        config_layout.setSpacing(4)
        
        config_edit = QLineEdit()
        config_edit.setPlaceholderText(f"~/.{agent_type}")
        config_edit.textChanged.connect(lambda: self.agents_changed.emit())
        
        browse_btn = QToolButton()
        browse_btn.setText("...")
        browse_btn.setFixedWidth(30)
        browse_btn.setProperty("instance_id", instance_id)  # Store instance_id
        browse_btn.clicked.connect(self._on_browse_clicked)
        
        config_layout.addWidget(config_edit)
        config_layout.addWidget(browse_btn)
        
        self._agent_table.setCellWidget(row, 1, config_widget)
        
        # Priority controls (up/down arrows)
        priority_widget = QWidget()
        priority_layout = QHBoxLayout(priority_widget)
        priority_layout.setContentsMargins(4, 2, 4, 2)
        priority_layout.setSpacing(4)

        up_btn = QToolButton()
        up_btn.setText("↑")
        up_btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
        up_btn.setProperty("instance_id", instance_id)  # Store instance_id
        up_btn.clicked.connect(self._on_up_clicked)

        down_btn = QToolButton()
        down_btn.setText("↓")
        down_btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
        down_btn.setProperty("instance_id", instance_id)  # Store instance_id
        down_btn.clicked.connect(self._on_down_clicked)

        priority_layout.addWidget(up_btn)
        priority_layout.addWidget(down_btn)
        priority_layout.addStretch(1)

        self._agent_table.setCellWidget(row, 2, priority_widget)
        
        # Fallback dropdown
        fallback_combo = QComboBox()
        fallback_combo.addItem("—", "")
        fallback_combo.currentIndexChanged.connect(lambda: self.agents_changed.emit())
        self._agent_table.setCellWidget(row, 3, fallback_combo)
        
        # Actions (Remove button)
        actions_widget = QWidget()
        actions_layout = QHBoxLayout(actions_widget)
        actions_layout.setContentsMargins(4, 2, 4, 2)
        actions_layout.setSpacing(4)
        
        remove_btn = QToolButton()
        remove_btn.setText("Remove")
        remove_btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
        remove_btn.setProperty("instance_id", instance_id)  # Store instance_id
        remove_btn.clicked.connect(self._on_remove_clicked)
        
        actions_layout.addWidget(remove_btn)
        actions_layout.addStretch(1)
        
        self._agent_table.setCellWidget(row, 4, actions_widget)
        
        # Empty column for spacing
        self._agent_table.setItem(row, 5, QTableWidgetItem(""))
        
        self._update_fallback_options()
        self._refresh_fallback_visibility()
        self.agents_changed.emit()

    def _find_row_by_instance_id(self, instance_id: str) -> int:
        """Find the row containing the given instance_id."""
        for row in range(self._agent_table.rowCount()):
            item = self._agent_table.item(row, 0)
            if item and item.data(Qt.UserRole) == instance_id:
                return row
        return -1

    def _on_browse_clicked(self) -> None:
        """Handle browse button click using instance_id property."""
        sender = self.sender()
        if sender:
            instance_id = sender.property("instance_id")
            if instance_id:
                row = self._find_row_by_instance_id(instance_id)
                if row >= 0:
                    self._browse_config_dir(row)

    def _on_up_clicked(self) -> None:
        """Handle up arrow click using instance_id property."""
        sender = self.sender()
        if sender:
            instance_id = sender.property("instance_id")
            if instance_id:
                row = self._find_row_by_instance_id(instance_id)
                if row >= 0:
                    self._move_agent_up(row)

    def _on_down_clicked(self) -> None:
        """Handle down arrow click using instance_id property."""
        sender = self.sender()
        if sender:
            instance_id = sender.property("instance_id")
            if instance_id:
                row = self._find_row_by_instance_id(instance_id)
                if row >= 0:
                    self._move_agent_down(row)

    def _on_remove_clicked(self) -> None:
        """Handle remove button click using instance_id property."""
        sender = self.sender()
        if sender:
            instance_id = sender.property("instance_id")
            if instance_id:
                row = self._find_row_by_instance_id(instance_id)
                if row >= 0:
                    self._remove_agent(row)

    def _remove_agent(self, row: int) -> None:
        """Remove an agent instance from the table."""
        if 0 <= row < self._agent_table.rowCount():
            self._agent_table.removeRow(row)
            self._update_fallback_options()
            self.agents_changed.emit()

    def _move_agent_up(self, row: int) -> None:
        """Move agent up in priority (swap with row above)."""
        if row <= 0:
            return
        self._swap_rows(row, row - 1)
        self._update_fallback_options()
        self.agents_changed.emit()

    def _move_agent_down(self, row: int) -> None:
        """Move agent down in priority (swap with row below)."""
        if row < 0 or row >= self._agent_table.rowCount() - 1:
            return
        self._swap_rows(row, row + 1)
        self._update_fallback_options()
        self.agents_changed.emit()

    def _swap_rows(self, row1: int, row2: int) -> None:
        """Swap two rows in the table."""
        if row1 < 0 or row2 < 0:
            return
        if row1 >= self._agent_table.rowCount() or row2 >= self._agent_table.rowCount():
            return
        
        # Get data from row1
        item1 = self._agent_table.item(row1, 0)
        if not item1:
            return
        instance_id1 = item1.data(Qt.UserRole)
        agent_type1 = item1.data(Qt.UserRole + 1)
        
        config_widget1 = self._agent_table.cellWidget(row1, 1)
        config_edit1 = config_widget1.findChild(QLineEdit) if config_widget1 else None
        config_value1 = config_edit1.text() if config_edit1 else ""
        
        fallback_combo1 = self._agent_table.cellWidget(row1, 3)
        fallback_value1 = fallback_combo1.currentData() if isinstance(fallback_combo1, QComboBox) else ""
        
        # Get data from row2
        item2 = self._agent_table.item(row2, 0)
        if not item2:
            return
        instance_id2 = item2.data(Qt.UserRole)
        agent_type2 = item2.data(Qt.UserRole + 1)
        
        config_widget2 = self._agent_table.cellWidget(row2, 1)
        config_edit2 = config_widget2.findChild(QLineEdit) if config_widget2 else None
        config_value2 = config_edit2.text() if config_edit2 else ""
        
        fallback_combo2 = self._agent_table.cellWidget(row2, 3)
        fallback_value2 = fallback_combo2.currentData() if isinstance(fallback_combo2, QComboBox) else ""
        
        # Swap data in row1
        item1.setText(agent_type2.title())
        item1.setData(Qt.UserRole, instance_id2)
        item1.setData(Qt.UserRole + 1, agent_type2)
        if config_edit1:
            config_edit1.setText(config_value2)
        if isinstance(fallback_combo1, QComboBox):
            idx = fallback_combo1.findData(fallback_value2)
            if idx >= 0:
                fallback_combo1.setCurrentIndex(idx)
        
        # Swap data in row2
        item2.setText(agent_type1.title())
        item2.setData(Qt.UserRole, instance_id1)
        item2.setData(Qt.UserRole + 1, agent_type1)
        if config_edit2:
            config_edit2.setText(config_value1)
        if isinstance(fallback_combo2, QComboBox):
            idx = fallback_combo2.findData(fallback_value1)
            if idx >= 0:
                fallback_combo2.setCurrentIndex(idx)

    def _browse_config_dir(self, row: int) -> None:
        """Open file dialog to select config directory."""
        if row < 0 or row >= self._agent_table.rowCount():
            return
        
        item = self._agent_table.item(row, 0)
        if not item:
            return
        agent_type = item.data(Qt.UserRole + 1)
        
        config_widget = self._agent_table.cellWidget(row, 1)
        config_edit = config_widget.findChild(QLineEdit) if config_widget else None
        if not config_edit:
            return
        
        current = config_edit.text() or os.path.expanduser(f"~/.{agent_type}")
        
        path = QFileDialog.getExistingDirectory(
            self,
            f"Select {agent_type.title()} Config Directory",
            current,
        )
        if path:
            config_edit.setText(path)

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
        """Update fallback dropdown options for all rows."""
        # Collect all instance IDs and types
        instances = []
        for row in range(self._agent_table.rowCount()):
            item = self._agent_table.item(row, 0)
            if item:
                instance_id = item.data(Qt.UserRole)
                agent_type = item.data(Qt.UserRole + 1)
                instances.append((row, instance_id, agent_type))
        
        # Update each fallback combo
        for row, instance_id, agent_type in instances:
            fallback_combo = self._agent_table.cellWidget(row, 3)
            if not isinstance(fallback_combo, QComboBox):
                continue
            
            current_value = fallback_combo.currentData()
            fallback_combo.blockSignals(True)
            fallback_combo.clear()
            fallback_combo.addItem("—", "")
            
            # Add other instances as fallback options (excluding self)
            for other_row, other_id, other_type in instances:
                if other_id != instance_id:
                    display_name = f"{other_type.title()} ({other_id[:8]}...)"
                    fallback_combo.addItem(display_name, other_id)
            
            # Restore previous selection if still valid
            if current_value:
                idx = fallback_combo.findData(current_value)
                if idx >= 0:
                    fallback_combo.setCurrentIndex(idx)
            
            fallback_combo.blockSignals(False)

    def set_agent_selection(self, agent_selection: AgentSelection | None) -> None:
        """Load agent selection into the UI."""
        # Clear existing rows
        self._agent_table.setRowCount(0)
        
        if agent_selection is None:
            self._selection_mode.blockSignals(True)
            self._selection_mode.setCurrentIndex(0)
            self._selection_mode.blockSignals(False)
            self._refresh_fallback_visibility()
            return
        
        # Load agent instances
        for instance in agent_selection.agent_instances:
            row = self._agent_table.rowCount()
            self._agent_table.insertRow(row)
            
            # Agent type
            type_item = QTableWidgetItem(instance.agent_type.title())
            type_item.setFlags(type_item.flags() & ~Qt.ItemIsEditable)
            type_item.setData(Qt.UserRole, instance.instance_id)
            type_item.setData(Qt.UserRole + 1, instance.agent_type)
            self._agent_table.setItem(row, 0, type_item)
            
            # Config directory
            config_widget = QWidget()
            config_layout = QHBoxLayout(config_widget)
            config_layout.setContentsMargins(4, 2, 4, 2)
            config_layout.setSpacing(4)
            
            config_edit = QLineEdit()
            config_edit.setPlaceholderText(f"~/.{instance.agent_type}")
            config_edit.setText(instance.config_dir)
            config_edit.textChanged.connect(lambda: self.agents_changed.emit())
            
            browse_btn = QToolButton()
            browse_btn.setText("...")
            browse_btn.setFixedWidth(30)
            browse_btn.setProperty("instance_id", instance.instance_id)
            browse_btn.clicked.connect(self._on_browse_clicked)
            
            config_layout.addWidget(config_edit)
            config_layout.addWidget(browse_btn)
            
            self._agent_table.setCellWidget(row, 1, config_widget)
            
            # Priority controls
            priority_widget = QWidget()
            priority_layout = QHBoxLayout(priority_widget)
            priority_layout.setContentsMargins(4, 2, 4, 2)
            priority_layout.setSpacing(4)

            up_btn = QToolButton()
            up_btn.setText("↑")
            up_btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
            up_btn.setProperty("instance_id", instance.instance_id)
            up_btn.clicked.connect(self._on_up_clicked)

            down_btn = QToolButton()
            down_btn.setText("↓")
            down_btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
            down_btn.setProperty("instance_id", instance.instance_id)
            down_btn.clicked.connect(self._on_down_clicked)

            priority_layout.addWidget(up_btn)
            priority_layout.addWidget(down_btn)
            priority_layout.addStretch(1)

            self._agent_table.setCellWidget(row, 2, priority_widget)
            
            # Fallback dropdown
            fallback_combo = QComboBox()
            fallback_combo.addItem("—", "")
            fallback_combo.currentIndexChanged.connect(lambda: self.agents_changed.emit())
            self._agent_table.setCellWidget(row, 3, fallback_combo)
            
            # Actions
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(4, 2, 4, 2)
            actions_layout.setSpacing(4)
            
            remove_btn = QToolButton()
            remove_btn.setText("Remove")
            remove_btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
            remove_btn.setProperty("instance_id", instance.instance_id)
            remove_btn.clicked.connect(self._on_remove_clicked)
            
            actions_layout.addWidget(remove_btn)
            actions_layout.addStretch(1)
            
            self._agent_table.setCellWidget(row, 4, actions_widget)
            
            # Empty column
            self._agent_table.setItem(row, 5, QTableWidgetItem(""))
        
        # Set selection mode
        idx = self._selection_mode.findData(agent_selection.selection_mode or "round-robin")
        self._selection_mode.blockSignals(True)
        if idx >= 0:
            self._selection_mode.setCurrentIndex(idx)
        else:
            self._selection_mode.setCurrentIndex(0)
        self._selection_mode.blockSignals(False)
        
        # Update fallback options and then set fallback values
        self._update_fallback_options()
        
        for i, instance in enumerate(agent_selection.agent_instances):
            if i < self._agent_table.rowCount():
                fallback_combo = self._agent_table.cellWidget(i, 3)
                if isinstance(fallback_combo, QComboBox) and instance.fallback_instance_id:
                    idx = fallback_combo.findData(instance.fallback_instance_id)
                    if idx >= 0:
                        fallback_combo.blockSignals(True)
                        fallback_combo.setCurrentIndex(idx)
                        fallback_combo.blockSignals(False)
        
        self._refresh_fallback_visibility()

    def get_agent_selection(self) -> AgentSelection | None:
        """Extract agent selection from the UI."""
        if self._agent_table.rowCount() == 0:
            return None
        
        agent_instances = []
        for row in range(self._agent_table.rowCount()):
            item = self._agent_table.item(row, 0)
            if not item:
                continue
            
            instance_id = item.data(Qt.UserRole)
            agent_type = item.data(Qt.UserRole + 1)
            
            config_widget = self._agent_table.cellWidget(row, 1)
            config_edit = config_widget.findChild(QLineEdit) if config_widget else None
            config_dir = os.path.expanduser(config_edit.text().strip()) if config_edit else ""
            
            fallback_combo = self._agent_table.cellWidget(row, 3)
            fallback_instance_id = ""
            if isinstance(fallback_combo, QComboBox):
                fallback_instance_id = str(fallback_combo.currentData() or "").strip()
            
            agent_instances.append(AgentInstance(
                instance_id=instance_id,
                agent_type=agent_type,
                config_dir=config_dir,
                fallback_instance_id=fallback_instance_id
            ))
        
        selection_mode = str(self._selection_mode.currentData() or "round-robin")
        
        return AgentSelection(
            agent_instances=agent_instances,
            selection_mode=selection_mode,
        )
