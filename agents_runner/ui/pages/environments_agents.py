from __future__ import annotations

import os
import re

from PySide6.QtCore import Qt
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QCheckBox
from PySide6.QtWidgets import QComboBox
from PySide6.QtWidgets import QFileDialog
from PySide6.QtWidgets import QHBoxLayout
from PySide6.QtWidgets import QHeaderView
from PySide6.QtWidgets import QLabel
from PySide6.QtWidgets import QLineEdit
from PySide6.QtWidgets import QMessageBox
from PySide6.QtWidgets import QScrollArea
from PySide6.QtWidgets import QSizePolicy
from PySide6.QtWidgets import QTableWidget
from PySide6.QtWidgets import QToolButton
from PySide6.QtWidgets import QVBoxLayout
from PySide6.QtWidgets import QWidget

from agents_runner.agent_cli import normalize_agent
from agents_runner.agent_cli import SUPPORTED_AGENTS
from agents_runner.environments.model import AgentInstance
from agents_runner.environments.model import AgentSelection
from agents_runner.ui.constants import (
    TAB_CONTENT_MARGINS,
    TAB_CONTENT_SPACING,
    BUTTON_ROW_SPACING,
    TABLE_ROW_HEIGHT,
    AGENT_COMBO_WIDTH,
)
from agents_runner.ui.dialogs.test_chain_dialog import TestChainDialog


_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


class AgentsTabWidget(QWidget):
    agents_changed = Signal()

    _COL_PRIORITY = 0
    _COL_AGENT = 1
    _COL_ID = 2
    _COL_CONFIG = 3
    _COL_CLI_FLAGS = 4
    _COL_FALLBACK = 5
    _COL_REMOVE = 6

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._rows: list[AgentInstance] = []
        self._fallbacks: dict[str, str] = {}
        self._cross_agents_enabled: bool = False
        self._cross_agent_allowlist: set[str] = set()
        self._allowlist_checkboxes: dict[str, QCheckBox] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(*TAB_CONTENT_MARGINS)
        layout.setSpacing(TAB_CONTENT_SPACING)

        header_label = QLabel(
            "Override the Settings agent configuration for this environment.\n"
            "Agents run in priority order (top to bottom). Add multiple entries per CLI to set fallbacks."
        )
        header_label.setStyleSheet("color: rgba(237, 239, 245, 160);")
        layout.addWidget(header_label)

        self._agent_table = QTableWidget()
        self._agent_table.setColumnCount(7)
        self._agent_table.setHorizontalHeaderLabels(
            ["Priority", "Agent", "ID", "Config folder", "CLI Flags", "Fallback", ""]
        )
        self._agent_table.horizontalHeader().setSectionResizeMode(
            self._COL_PRIORITY, QHeaderView.ResizeToContents
        )
        self._agent_table.horizontalHeader().setSectionResizeMode(
            self._COL_AGENT, QHeaderView.Interactive
        )
        self._agent_table.setColumnWidth(self._COL_AGENT, AGENT_COMBO_WIDTH)
        self._agent_table.horizontalHeader().setSectionResizeMode(
            self._COL_ID, QHeaderView.ResizeToContents
        )
        self._agent_table.horizontalHeader().setSectionResizeMode(
            self._COL_CONFIG, QHeaderView.Stretch
        )
        self._agent_table.horizontalHeader().setSectionResizeMode(
            self._COL_CLI_FLAGS, QHeaderView.Stretch
        )
        self._agent_table.horizontalHeader().setSectionResizeMode(
            self._COL_FALLBACK, QHeaderView.ResizeToContents
        )
        self._agent_table.horizontalHeader().setSectionResizeMode(
            self._COL_REMOVE, QHeaderView.ResizeToContents
        )
        self._agent_table.verticalHeader().setVisible(False)
        self._agent_table.verticalHeader().setMinimumSectionSize(TABLE_ROW_HEIGHT)
        self._agent_table.verticalHeader().setDefaultSectionSize(TABLE_ROW_HEIGHT)
        self._agent_table.setSelectionMode(QTableWidget.NoSelection)
        self._agent_table.setFocusPolicy(Qt.NoFocus)
        self._agent_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self._agent_table, 1)

        # Controls row under table with :: separators
        controls_container = QWidget(self)
        controls_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        controls_row = QHBoxLayout(controls_container)
        controls_row.setContentsMargins(0, 0, 0, 0)
        controls_row.setSpacing(BUTTON_ROW_SPACING)

        # Add agent controls
        controls_row.addWidget(QLabel("Add agent"))
        self._add_agent_cli = QComboBox()
        for agent in SUPPORTED_AGENTS:
            self._add_agent_cli.addItem(agent.title(), agent)
        controls_row.addWidget(self._add_agent_cli)

        add_btn = QToolButton()
        add_btn.setText("Add")
        add_btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
        add_btn.clicked.connect(self._on_add_agent)
        controls_row.addWidget(add_btn)

        # Separator
        sep1 = QLabel("::")
        sep1.setStyleSheet("color: rgba(237, 239, 245, 160); margin-left: 6px; margin-right: 4px;")
        controls_row.addWidget(sep1)

        # Selection mode controls
        controls_row.addWidget(QLabel("Selection mode"))
        self._selection_mode = QComboBox()
        self._selection_mode.addItem("Round-robin", "round-robin")
        self._selection_mode.addItem("Least used (active tasks)", "least-used")
        self._selection_mode.addItem("Fallback (show mapping)", "fallback")
        self._selection_mode.setMaximumWidth(340)
        self._selection_mode.currentIndexChanged.connect(
            self._on_selection_mode_changed
        )
        controls_row.addWidget(self._selection_mode)

        # Separator
        sep2 = QLabel("::")
        sep2.setStyleSheet("color: rgba(237, 239, 245, 160); margin-left: 6px; margin-right: 4px;")
        controls_row.addWidget(sep2)

        # Test Chain button
        test_chain_btn = QToolButton()
        test_chain_btn.setText("Test Chain")
        test_chain_btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
        test_chain_btn.clicked.connect(self._on_test_chain)
        controls_row.addWidget(test_chain_btn)

        controls_row.addStretch(1)
        layout.addWidget(controls_container, 0)

        # Cross-agent allowlist section (hidden by default)
        from agents_runner.widgets import GlassCard
        self._cross_agents_card = GlassCard()
        self._cross_agents_card.setVisible(False)
        cross_agents_layout = QVBoxLayout(self._cross_agents_card)
        cross_agents_layout.setContentsMargins(18, 16, 18, 16)
        cross_agents_layout.setSpacing(10)
        
        cross_agents_header = QLabel("Cross-agent allowlist")
        cross_agents_header.setStyleSheet("font-size: 14px; font-weight: 650;")
        cross_agents_layout.addWidget(cross_agents_header)
        
        cross_agents_desc = QLabel(
            "Select agent instances to mount as cross-agents in task containers.\n"
            "Only one instance per CLI can be selected (enforced by disabling duplicates)."
        )
        cross_agents_desc.setStyleSheet("color: rgba(237, 239, 245, 160);")
        cross_agents_desc.setWordWrap(True)
        cross_agents_layout.addWidget(cross_agents_desc)
        
        # Scrollable container for checkboxes
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setMinimumHeight(150)
        scroll.setMaximumHeight(250)
        
        self._allowlist_container = QWidget()
        self._allowlist_layout = QVBoxLayout(self._allowlist_container)
        self._allowlist_layout.setContentsMargins(0, 0, 0, 0)
        self._allowlist_layout.setSpacing(8)
        self._allowlist_layout.addStretch(1)
        
        scroll.setWidget(self._allowlist_container)
        cross_agents_layout.addWidget(scroll, 1)
        
        layout.addWidget(self._cross_agents_card, 0)

        self._refresh_fallback_visibility()
        self._render_table()

    def _sanitize_agent_id(self, value: str) -> str:
        v = (value or "").strip().lower()
        v = re.sub(r"[^a-z0-9_-]+", "-", v).strip("-_")
        return v

    def _generate_agent_id(self, agent_cli: str) -> str:
        base = normalize_agent(agent_cli)
        existing = {a.agent_id for a in self._rows}
        if base not in existing:
            return base
        i = 2
        while True:
            candidate = f"{base}-{i}"
            if candidate not in existing:
                return candidate
            i += 1

    def _on_add_agent(self) -> None:
        agent_cli = normalize_agent(str(self._add_agent_cli.currentData() or "codex"))
        agent_id = self._generate_agent_id(agent_cli)
        self._rows.append(
            AgentInstance(
                agent_id=agent_id, agent_cli=agent_cli, config_dir="", cli_flags=""
            )
        )
        self._render_table()
        self._update_fallback_options()
        self.agents_changed.emit()

    def _on_selection_mode_changed(self, _index: int) -> None:
        self._refresh_fallback_visibility()
        self.agents_changed.emit()

    def _refresh_fallback_visibility(self) -> None:
        is_fallback_mode = (
            str(self._selection_mode.currentData() or "round-robin") == "fallback"
        )
        self._agent_table.setColumnHidden(self._COL_FALLBACK, not is_fallback_mode)

    def _refresh_priority_visibility(self) -> None:
        self._agent_table.setColumnHidden(self._COL_PRIORITY, len(self._rows) <= 1)

    def _render_table(self) -> None:
        self._agent_table.setRowCount(len(self._rows))
        self._agent_table.setMinimumHeight(1)

        for row_index, inst in enumerate(self._rows):
            self._agent_table.setRowHeight(row_index, TABLE_ROW_HEIGHT)
            self._agent_table.setCellWidget(
                row_index, self._COL_PRIORITY, self._priority_widget(row_index)
            )
            self._agent_table.setCellWidget(
                row_index, self._COL_AGENT, self._agent_cli_widget(row_index, inst)
            )
            self._agent_table.setCellWidget(
                row_index, self._COL_ID, self._agent_id_widget(row_index, inst)
            )
            self._agent_table.setCellWidget(
                row_index, self._COL_CONFIG, self._config_dir_widget(row_index, inst)
            )
            self._agent_table.setCellWidget(
                row_index, self._COL_CLI_FLAGS, self._cli_flags_widget(row_index, inst)
            )
            self._agent_table.setCellWidget(
                row_index, self._COL_FALLBACK, self._fallback_widget(row_index, inst)
            )
            self._agent_table.setCellWidget(
                row_index, self._COL_REMOVE, self._remove_widget(row_index)
            )

        self._update_fallback_options()
        self._refresh_priority_visibility()
        self._refresh_fallback_visibility()
        
        # Refresh cross-agent allowlist UI if enabled
        if self._cross_agents_enabled:
            self._refresh_allowlist_ui()

    def _on_test_chain(self) -> None:
        """Handle test chain button click."""
        # Build agent list
        agent_names = [a.agent_cli for a in self._rows]
        if not agent_names:
            QMessageBox.information(
                self,
                "No agents configured",
                "Add at least one agent to test the chain.",
            )
            return
        
        # Show test dialog
        dialog = TestChainDialog(agent_names, cooldown_manager=None, parent=self)
        dialog.exec()

    def _priority_widget(self, row_index: int) -> QWidget:
        w = QWidget()
        layout = QHBoxLayout(w)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(8)

        up_btn = QToolButton()
        up_btn.setText("Up")
        up_btn.setArrowType(Qt.UpArrow)
        up_btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        up_btn.setMinimumWidth(68)
        up_btn.setEnabled(row_index > 0)
        up_btn.setToolTip("Move up (higher priority)")
        up_btn.clicked.connect(lambda: self._move_row(row_index, -1))

        down_btn = QToolButton()
        down_btn.setText("Down")
        down_btn.setArrowType(Qt.DownArrow)
        down_btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        down_btn.setMinimumWidth(68)
        down_btn.setEnabled(row_index < len(self._rows) - 1)
        down_btn.setToolTip("Move down (lower priority)")
        down_btn.clicked.connect(lambda: self._move_row(row_index, 1))

        layout.addWidget(up_btn)
        layout.addWidget(down_btn)
        return w

    def _move_row(self, row_index: int, delta: int) -> None:
        new_index = row_index + int(delta)
        if (
            row_index < 0
            or new_index < 0
            or row_index >= len(self._rows)
            or new_index >= len(self._rows)
        ):
            return
        self._rows[row_index], self._rows[new_index] = (
            self._rows[new_index],
            self._rows[row_index],
        )
        self._render_table()
        self.agents_changed.emit()

    def _agent_cli_widget(self, row_index: int, inst: AgentInstance) -> QWidget:
        label = QLabel(normalize_agent(inst.agent_cli).title())
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("color: rgba(237, 239, 245, 200);")
        return label

    def _agent_id_widget(self, row_index: int, inst: AgentInstance) -> QWidget:
        line = QLineEdit()
        line.setText(inst.agent_id)
        line.setPlaceholderText("id (unique)")
        line.editingFinished.connect(lambda: self._commit_row_agent_id(row_index, line))
        return line

    def _commit_row_agent_id(self, row_index: int, line: QLineEdit) -> None:
        if row_index < 0 or row_index >= len(self._rows):
            return
        current = self._rows[row_index]
        old_id = current.agent_id
        new_id = self._sanitize_agent_id(line.text())
        if not new_id:
            line.setText(old_id)
            return
        if not _ID_RE.match(new_id):
            QMessageBox.warning(
                self, "Invalid ID", "Agent ID must match: [a-z0-9][a-z0-9_-]{0,63}"
            )
            line.setText(old_id)
            return
        if any(
            a.agent_id == new_id for i, a in enumerate(self._rows) if i != row_index
        ):
            QMessageBox.warning(
                self,
                "Duplicate ID",
                f"Agent ID '{new_id}' is already used in this environment.",
            )
            line.setText(old_id)
            return
        if new_id == old_id:
            return

        updated_fallbacks: dict[str, str] = {}
        for k, v in self._fallbacks.items():
            kk = new_id if k == old_id else k
            vv = new_id if v == old_id else v
            if kk and vv and kk != vv:
                updated_fallbacks[kk] = vv
        self._fallbacks = updated_fallbacks
        
        # Update cross-agent allowlist
        if old_id in self._cross_agent_allowlist:
            self._cross_agent_allowlist.discard(old_id)
            self._cross_agent_allowlist.add(new_id)
        
        self._rows[row_index] = AgentInstance(
            agent_id=new_id,
            agent_cli=current.agent_cli,
            config_dir=current.config_dir,
            cli_flags=current.cli_flags,
        )
        self._render_table()
        self.agents_changed.emit()

    def _config_dir_widget(self, row_index: int, inst: AgentInstance) -> QWidget:
        w = QWidget()
        layout = QHBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        line = QLineEdit()
        line.setText(inst.config_dir)
        line.setPlaceholderText("Inherit Settings (leave blank)")
        line.editingFinished.connect(
            lambda: self._commit_row_config_dir(row_index, line)
        )

        browse = QToolButton()
        browse.setText("Browse…")
        browse.setToolButtonStyle(Qt.ToolButtonTextOnly)
        browse.clicked.connect(lambda: self._browse_row_config_dir(row_index, line))

        layout.addWidget(line, 1)
        layout.addWidget(browse)
        return w

    def _commit_row_config_dir(self, row_index: int, line: QLineEdit) -> None:
        if row_index < 0 or row_index >= len(self._rows):
            return
        inst = self._rows[row_index]
        value = os.path.expanduser(str(line.text() or "").strip())
        self._rows[row_index] = AgentInstance(
            agent_id=inst.agent_id,
            agent_cli=inst.agent_cli,
            config_dir=value,
            cli_flags=inst.cli_flags,
        )
        self.agents_changed.emit()

    def _browse_row_config_dir(self, row_index: int, line: QLineEdit) -> None:
        if row_index < 0 or row_index >= len(self._rows):
            return
        inst = self._rows[row_index]
        current = line.text() or os.path.expanduser(inst.config_dir or "~")
        path = QFileDialog.getExistingDirectory(
            self, "Select Agent Config folder", current
        )
        if path:
            line.setText(path)
            self._commit_row_config_dir(row_index, line)

    def _cli_flags_widget(self, row_index: int, inst: AgentInstance) -> QWidget:
        line = QLineEdit()
        line.setText(inst.cli_flags)
        line.setPlaceholderText("--model … (optional)")
        line.setToolTip("Extra CLI flags appended to this agent command")
        line.editingFinished.connect(
            lambda: self._commit_row_cli_flags(row_index, line)
        )
        return line

    def _commit_row_cli_flags(self, row_index: int, line: QLineEdit) -> None:
        if row_index < 0 or row_index >= len(self._rows):
            return
        inst = self._rows[row_index]
        value = str(line.text() or "").strip()
        self._rows[row_index] = AgentInstance(
            agent_id=inst.agent_id,
            agent_cli=inst.agent_cli,
            config_dir=inst.config_dir,
            cli_flags=value,
        )
        self.agents_changed.emit()

    def _fallback_widget(self, row_index: int, inst: AgentInstance) -> QWidget:
        combo = QComboBox()
        combo.addItem("—", "")
        combo.currentIndexChanged.connect(
            lambda _i: self._commit_row_fallback(row_index, combo)
        )
        return combo

    def _commit_row_fallback(self, row_index: int, combo: QComboBox) -> None:
        if row_index < 0 or row_index >= len(self._rows):
            return
        inst = self._rows[row_index]
        fallback_id = str(combo.currentData() or "").strip()
        if fallback_id:
            self._fallbacks[inst.agent_id] = fallback_id
        else:
            self._fallbacks.pop(inst.agent_id, None)
        self.agents_changed.emit()

    def _remove_widget(self, row_index: int) -> QWidget:
        btn = QToolButton()
        btn.setObjectName("RowTrash")
        btn.setText("✕")
        btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
        btn.clicked.connect(lambda: self._remove_row(row_index))
        return btn

    def _remove_row(self, row_index: int) -> None:
        if row_index < 0 or row_index >= len(self._rows):
            return
        removed_id = self._rows[row_index].agent_id
        self._rows.pop(row_index)
        self._fallbacks.pop(removed_id, None)
        for k, v in list(self._fallbacks.items()):
            if v == removed_id:
                self._fallbacks.pop(k, None)
        
        # Remove from cross-agent allowlist
        self._cross_agent_allowlist.discard(removed_id)
        
        self._render_table()
        self.agents_changed.emit()

    def _update_fallback_options(self) -> None:
        ids = [a.agent_id for a in self._rows]
        for row_index, inst in enumerate(self._rows):
            combo = self._agent_table.cellWidget(row_index, self._COL_FALLBACK)
            if not isinstance(combo, QComboBox):
                continue
            current_value = str(self._fallbacks.get(inst.agent_id, "") or "").strip()
            combo.blockSignals(True)
            combo.clear()
            combo.addItem("—", "")
            for other in self._rows:
                if other.agent_id == inst.agent_id:
                    continue
                combo.addItem(
                    f"{other.agent_id} ({normalize_agent(other.agent_cli)})",
                    other.agent_id,
                )
            if current_value and current_value in ids:
                idx = combo.findData(current_value)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
            combo.blockSignals(False)

    def set_agent_selection(self, agent_selection: AgentSelection | None) -> None:
        self._selection_mode.blockSignals(True)
        try:
            if agent_selection is None:
                self._rows = []
                self._fallbacks = {}
                self._selection_mode.setCurrentIndex(0)
            else:
                self._rows = [
                    AgentInstance(
                        agent_id=str(a.agent_id or "").strip(),
                        agent_cli=normalize_agent(str(a.agent_cli or "")),
                        config_dir=str(getattr(a, "config_dir", "") or "").strip(),
                        cli_flags=str(getattr(a, "cli_flags", "") or "").strip(),
                    )
                    for a in (agent_selection.agents or [])
                    if str(getattr(a, "agent_id", "") or "").strip()
                ]
                self._fallbacks = dict(agent_selection.agent_fallbacks or {})
                idx = self._selection_mode.findData(
                    str(agent_selection.selection_mode or "round-robin")
                )
                self._selection_mode.setCurrentIndex(idx if idx >= 0 else 0)
        finally:
            self._selection_mode.blockSignals(False)

        self._render_table()
        self._refresh_fallback_visibility()
        self._refresh_priority_visibility()

    def get_agent_selection(self) -> AgentSelection | None:
        agents: list[AgentInstance] = []
        for inst in self._rows:
            agent_id = str(inst.agent_id or "").strip()
            agent_cli = normalize_agent(str(inst.agent_cli or "codex"))
            config_dir = os.path.expanduser(str(inst.config_dir or "").strip())
            cli_flags = str(inst.cli_flags or "").strip()
            if agent_id:
                agents.append(
                    AgentInstance(
                        agent_id=agent_id,
                        agent_cli=agent_cli,
                        config_dir=config_dir,
                        cli_flags=cli_flags,
                    )
                )

        if not agents:
            return None

        known_ids = {a.agent_id for a in agents}
        cleaned_fallbacks: dict[str, str] = {}
        for k, v in (self._fallbacks or {}).items():
            kk = str(k or "").strip()
            vv = str(v or "").strip()
            if kk in known_ids and vv in known_ids and kk != vv:
                cleaned_fallbacks[kk] = vv

        return AgentSelection(
            agents=agents,
            selection_mode=str(self._selection_mode.currentData() or "round-robin"),
            agent_fallbacks=cleaned_fallbacks,
        )

    def set_cross_agents_enabled(self, enabled: bool) -> None:
        """Show/hide the cross-agent allowlist UI section."""
        self._cross_agents_enabled = enabled
        self._cross_agents_card.setVisible(enabled)
        if enabled:
            self._refresh_allowlist_ui()

    def set_cross_agent_allowlist(self, allowlist: list[str]) -> None:
        """Set the cross-agent allowlist from saved data."""
        self._cross_agent_allowlist = set(allowlist or [])
        if self._cross_agents_enabled:
            self._refresh_allowlist_ui()

    def get_cross_agent_allowlist(self) -> list[str]:
        """Return the cross-agent allowlist as a list of agent_ids."""
        # Filter to only include agent_ids that still exist
        known_ids = {a.agent_id for a in self._rows}
        return [aid for aid in sorted(self._cross_agent_allowlist) if aid in known_ids]

    def _refresh_allowlist_ui(self) -> None:
        """Rebuild the cross-agent allowlist checkboxes from current agent rows."""
        # Clear existing checkboxes
        while self._allowlist_layout.count() > 1:  # Keep the stretch
            item = self._allowlist_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        self._allowlist_checkboxes.clear()
        
        if not self._rows:
            no_agents_label = QLabel("No agents configured. Add agents above first.")
            no_agents_label.setStyleSheet("color: rgba(237, 239, 245, 160); font-style: italic;")
            self._allowlist_layout.insertWidget(0, no_agents_label)
            return
        
        # Build a map of agent_cli to list of agent instances
        cli_to_instances: dict[str, list[AgentInstance]] = {}
        for inst in self._rows:
            cli = normalize_agent(inst.agent_cli)
            if cli not in cli_to_instances:
                cli_to_instances[cli] = []
            cli_to_instances[cli].append(inst)
        
        # Create checkboxes for each agent instance
        for inst in self._rows:
            cli = normalize_agent(inst.agent_cli)
            
            checkbox = QCheckBox()
            checkbox.setText(f"{inst.agent_id} ({cli})")
            if inst.config_dir:
                checkbox.setToolTip(f"Agent CLI: {cli}\nConfig: {inst.config_dir}")
            else:
                checkbox.setToolTip(f"Agent CLI: {cli}\nConfig: Inherit Settings")
            
            # Set checked state
            checkbox.setChecked(inst.agent_id in self._cross_agent_allowlist)
            
            # Connect to handler
            checkbox.stateChanged.connect(
                lambda state, aid=inst.agent_id: self._on_allowlist_checkbox_changed(aid, state)
            )
            
            self._allowlist_checkboxes[inst.agent_id] = checkbox
            self._allowlist_layout.insertWidget(self._allowlist_layout.count() - 1, checkbox)
        
        # Apply "one instance per CLI" validation
        self._update_allowlist_validation()

    def _on_allowlist_checkbox_changed(self, agent_id: str, state: int) -> None:
        """Handle allowlist checkbox state change."""
        is_checked = state == Qt.CheckState.Checked.value
        
        if is_checked:
            self._cross_agent_allowlist.add(agent_id)
        else:
            self._cross_agent_allowlist.discard(agent_id)
        
        # Update validation to enforce "one instance per CLI"
        self._update_allowlist_validation()

    def _update_allowlist_validation(self) -> None:
        """Enforce 'one instance per CLI' rule in allowlist UI."""
        # Build map of agent_cli to agent_ids that are checked
        cli_to_checked: dict[str, list[str]] = {}
        for inst in self._rows:
            cli = normalize_agent(inst.agent_cli)
            if inst.agent_id in self._cross_agent_allowlist:
                if cli not in cli_to_checked:
                    cli_to_checked[cli] = []
                cli_to_checked[cli].append(inst.agent_id)
        
        # Disable/enable checkboxes based on validation
        for inst in self._rows:
            checkbox = self._allowlist_checkboxes.get(inst.agent_id)
            if not checkbox:
                continue
            
            cli = normalize_agent(inst.agent_cli)
            checked_for_cli = cli_to_checked.get(cli, [])
            
            if inst.agent_id in self._cross_agent_allowlist:
                # This checkbox is checked, keep it enabled
                checkbox.setEnabled(True)
            elif len(checked_for_cli) > 0:
                # Another instance of same CLI is checked, disable this one
                checkbox.setEnabled(False)
            else:
                # No instance of this CLI is checked, enable this one
                checkbox.setEnabled(True)
