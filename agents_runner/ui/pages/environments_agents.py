from __future__ import annotations

import re

from PySide6.QtCore import QSize
from PySide6.QtCore import Qt
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QCheckBox
from PySide6.QtWidgets import QComboBox
from PySide6.QtWidgets import QHBoxLayout
from PySide6.QtWidgets import QHeaderView
from PySide6.QtWidgets import QLabel
from PySide6.QtWidgets import QMessageBox
from PySide6.QtWidgets import QSizePolicy
from PySide6.QtWidgets import QTableWidget
from PySide6.QtWidgets import QToolButton
from PySide6.QtWidgets import QVBoxLayout
from PySide6.QtWidgets import QWidget

from agents_runner.agent_configs.storage import load_agent_configs
from agents_runner.environments.model import AgentInstance
from agents_runner.environments.model import AgentSelection
from agents_runner.persistence import default_state_path
from agents_runner.ui.constants import (
    AGENT_COMBO_WIDTH,
    BUTTON_ROW_SPACING,
    TAB_CONTENT_MARGINS,
    TAB_CONTENT_SPACING,
    TABLE_ROW_HEIGHT,
)
from agents_runner.ui.dialogs.test_chain_dialog import TestChainDialog
from agents_runner.ui.lucide_icons import lucide_icon


class AgentsTabWidget(QWidget):
    agent_changed = Signal()
    agents_changed = Signal()

    _COL_PRIORITY = 0
    _COL_CONFIG_ID = 1
    _COL_FALLBACK = 2
    _COL_CROSS_AGENT = 3
    _COL_REMOVE = 4

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._state_path: str = ""
        self._rows: list[AgentInstance] = []
        self._fallbacks: dict[str, str] = {}
        self._pinned_agent_id: str = ""
        self._cross_agents_enabled: bool = False
        self._cross_agent_allowlist: set[str] = set()
        self._allowlist_checkboxes: dict[str, QCheckBox] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(*TAB_CONTENT_MARGINS)
        layout.setSpacing(TAB_CONTENT_SPACING)

        header_label = QLabel(
            "Override the Settings agent configuration for this environment.\n"
            "Agents run in priority order (top to bottom) using saved config IDs."
        )
        header_label.setStyleSheet("color: rgba(237, 239, 245, 160);")
        layout.addWidget(header_label)

        self._agent_table = QTableWidget()
        self._agent_table.setColumnCount(5)
        self._agent_table.setHorizontalHeaderLabels(["Priority", "Config ID", "Fallback", "Cross", ""])
        self._agent_table.horizontalHeader().setSectionResizeMode(
            self._COL_PRIORITY, QHeaderView.ResizeMode.ResizeToContents
        )
        self._agent_table.horizontalHeader().setSectionResizeMode(self._COL_CONFIG_ID, QHeaderView.ResizeMode.Stretch)
        self._agent_table.horizontalHeader().setSectionResizeMode(
            self._COL_FALLBACK, QHeaderView.ResizeMode.ResizeToContents
        )
        self._agent_table.horizontalHeader().setSectionResizeMode(
            self._COL_CROSS_AGENT, QHeaderView.ResizeMode.ResizeToContents
        )
        self._agent_table.horizontalHeader().setSectionResizeMode(
            self._COL_REMOVE, QHeaderView.ResizeMode.ResizeToContents
        )
        self._agent_table.verticalHeader().setVisible(False)
        self._agent_table.verticalHeader().setMinimumSectionSize(TABLE_ROW_HEIGHT)
        self._agent_table.verticalHeader().setDefaultSectionSize(TABLE_ROW_HEIGHT)
        self._agent_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self._agent_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._agent_table.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        layout.addWidget(self._agent_table, 1)

        controls_container = QWidget(self)
        controls_container.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        controls_row = QHBoxLayout(controls_container)
        controls_row.setContentsMargins(0, 0, 0, 0)
        controls_row.setSpacing(BUTTON_ROW_SPACING)

        controls_row.addWidget(QLabel("Add agent"))
        self._add_agent_config_id = QComboBox()
        self._add_agent_config_id.setMinimumWidth(AGENT_COMBO_WIDTH)
        controls_row.addWidget(self._add_agent_config_id)

        self._add_agent_btn = QToolButton()
        self._add_agent_btn.setText("Add")
        self._add_agent_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self._add_agent_btn.clicked.connect(self._on_add_agent)
        controls_row.addWidget(self._add_agent_btn)

        sep1 = QLabel("::")
        sep1.setStyleSheet("color: rgba(237, 239, 245, 160); margin-left: 6px; margin-right: 4px;")
        controls_row.addWidget(sep1)

        controls_row.addWidget(QLabel("Selection mode"))
        self._selection_mode = QComboBox()
        self._selection_mode.addItem("Round-robin", "round-robin")
        self._selection_mode.addItem("Least used (active tasks)", "least-used")
        self._selection_mode.addItem("Fallback (show mapping)", "fallback")
        self._selection_mode.addItem("Pinned (use one agent)", "pinned")
        self._selection_mode.setMaximumWidth(340)
        self._selection_mode.currentIndexChanged.connect(self._on_selection_mode_changed)
        controls_row.addWidget(self._selection_mode)

        self._pinned_agent_label = QLabel("Pinned agent")
        controls_row.addWidget(self._pinned_agent_label)

        self._pinned_agent = QComboBox()
        self._pinned_agent.setMaximumWidth(320)
        self._pinned_agent.currentIndexChanged.connect(self._on_pinned_agent_changed)
        controls_row.addWidget(self._pinned_agent)

        sep2 = QLabel("::")
        sep2.setStyleSheet("color: rgba(237, 239, 245, 160); margin-left: 6px; margin-right: 4px;")
        controls_row.addWidget(sep2)

        test_chain_btn = QToolButton()
        test_chain_btn.setText("Test Chain")
        test_chain_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        test_chain_btn.clicked.connect(self._on_test_chain)
        controls_row.addWidget(test_chain_btn)

        controls_row.addStretch(1)
        layout.addWidget(controls_container, 0)

        self._refresh_fallback_visibility()
        self._refresh_pinned_visibility()
        self._refresh_cross_agent_visibility()
        self._render_table()

    def set_state_path(self, state_path: str) -> None:
        self._state_path = str(state_path or "").strip()
        self._render_table()

    def _resolve_state_path(self) -> str:
        state_path = str(getattr(self, "_state_path", "") or "").strip()
        if state_path:
            return state_path

        window = self.window()
        state_path = str(getattr(window, "_state_path", "") or "").strip()
        if state_path:
            return state_path

        return default_state_path()

    @staticmethod
    def _sanitize_agent_id_base(value: str) -> str:
        base = re.sub(r"[^a-z0-9_-]+", "-", str(value or "").strip().lower())
        return base.strip("-_") or "agent"

    def _next_unique_agent_id(self, base: str, existing: set[str]) -> str:
        candidate = self._sanitize_agent_id_base(base)
        if candidate not in existing:
            existing.add(candidate)
            return candidate

        suffix = 2
        while True:
            numbered = f"{candidate}-{suffix}"
            if numbered not in existing:
                existing.add(numbered)
                return numbered
            suffix += 1

    def _generate_agent_id(self, base: str, *, exclude_row: int | None = None) -> str:
        existing = {
            inst.agent_id
            for row_index, inst in enumerate(self._rows)
            if row_index != exclude_row and str(inst.agent_id or "").strip()
        }
        return self._next_unique_agent_id(base, existing)

    def _load_configs(self) -> list[tuple[str, str]]:
        try:
            configs = load_agent_configs(self._resolve_state_path())
        except Exception:
            return []

        items: list[tuple[str, str]] = []
        seen: set[str] = set()
        for config in configs:
            config_id = str(getattr(config, "config_id", "") or "").strip()
            if not config_id or config_id in seen:
                continue
            items.append(
                (
                    config_id,
                    str(getattr(config, "agent_cli", "") or "").strip().lower(),
                )
            )
            seen.add(config_id)
        return items

    def _load_config_cli_map(self) -> dict[str, str]:
        return {config_id: agent_cli for config_id, agent_cli in self._load_configs()}

    def _config_ids_in_use(self, *, exclude_row: int | None = None) -> set[str]:
        return {
            str(inst.config_id or "").strip()
            for row_index, inst in enumerate(self._rows)
            if row_index != exclude_row and str(inst.config_id or "").strip()
        }

    @staticmethod
    def _row_display_label(inst: AgentInstance) -> str:
        config_id = str(inst.config_id or "").strip()
        agent_id = str(inst.agent_id or "").strip()
        return config_id or agent_id or "—"

    def _config_combo_label(self, config_id: str, *, missing: bool = False) -> str:
        label = str(config_id or "").strip() or "—"
        if missing and config_id:
            return f"{label} (missing)"
        return label

    def _on_add_agent(self) -> None:
        config_id = str(self._add_agent_config_id.currentData() or "").strip()
        if not config_id or config_id in self._config_ids_in_use():
            return

        self._rows.append(
            AgentInstance(
                agent_id=self._generate_agent_id(config_id),
                config_id=config_id,
            )
        )
        self._render_table()
        self._emit_agents_changed()

    def _on_selection_mode_changed(self, _index: int) -> None:
        self._refresh_fallback_visibility()
        self._refresh_pinned_visibility()
        self._ensure_pinned_default()
        self._emit_agents_changed()

    def _emit_agents_changed(self) -> None:
        self.agent_changed.emit()
        self.agents_changed.emit()

    def _refresh_fallback_visibility(self) -> None:
        is_fallback_mode = str(self._selection_mode.currentData() or "round-robin") == "fallback"
        self._agent_table.setColumnHidden(self._COL_FALLBACK, not is_fallback_mode)

    def _refresh_pinned_visibility(self) -> None:
        is_pinned_mode = str(self._selection_mode.currentData() or "") == "pinned"
        self._pinned_agent_label.setVisible(is_pinned_mode)
        self._pinned_agent.setVisible(is_pinned_mode)

    def _ensure_pinned_default(self) -> None:
        if str(self._selection_mode.currentData() or "") != "pinned":
            return
        ids = [a.agent_id for a in self._rows]
        if not ids:
            self._pinned_agent_id = ""
            return
        if self._pinned_agent_id and self._pinned_agent_id in ids:
            return
        self._pinned_agent_id = ids[0]
        self._update_pinned_options()

    def _refresh_priority_visibility(self) -> None:
        self._agent_table.setColumnHidden(self._COL_PRIORITY, len(self._rows) <= 1)

    def _refresh_cross_agent_visibility(self) -> None:
        self._agent_table.setColumnHidden(self._COL_CROSS_AGENT, not self._cross_agents_enabled)

    def _render_table(self) -> None:
        config_options = self._load_configs()
        self._agent_table.clearContents()
        self._agent_table.setRowCount(len(self._rows))
        self._agent_table.setMinimumHeight(1)
        self._allowlist_checkboxes.clear()

        for row_index, inst in enumerate(self._rows):
            self._agent_table.setRowHeight(row_index, TABLE_ROW_HEIGHT)
            self._agent_table.setCellWidget(row_index, self._COL_PRIORITY, self._priority_widget(row_index))
            self._agent_table.setCellWidget(
                row_index,
                self._COL_CONFIG_ID,
                self._config_id_widget(row_index, inst, config_options),
            )
            self._agent_table.setCellWidget(row_index, self._COL_FALLBACK, self._fallback_widget(row_index))
            self._agent_table.setCellWidget(row_index, self._COL_CROSS_AGENT, self._cross_agent_widget(inst))
            self._agent_table.setCellWidget(row_index, self._COL_REMOVE, self._remove_widget(row_index))

        self._update_fallback_options()
        self._update_pinned_options()
        self._refresh_add_agent_options(config_options)
        self._refresh_priority_visibility()
        self._refresh_fallback_visibility()
        self._refresh_pinned_visibility()
        self._refresh_cross_agent_visibility()
        if self._cross_agents_enabled:
            self._update_allowlist_validation()

    def _refresh_add_agent_options(self, config_options: list[tuple[str, str]] | None = None) -> None:
        available = config_options if config_options is not None else self._load_configs()
        used_config_ids = self._config_ids_in_use()
        current = str(self._add_agent_config_id.currentData() or "").strip()
        has_choices = False

        self._add_agent_config_id.blockSignals(True)
        try:
            self._add_agent_config_id.clear()
            for config_id, _agent_cli in available:
                if config_id in used_config_ids:
                    continue
                self._add_agent_config_id.addItem(config_id, config_id)

            has_choices = self._add_agent_config_id.count() > 0
            if not has_choices:
                self._add_agent_config_id.addItem("No saved configs", "")
            elif current:
                idx = self._add_agent_config_id.findData(current)
                if idx >= 0:
                    self._add_agent_config_id.setCurrentIndex(idx)
        finally:
            self._add_agent_config_id.blockSignals(False)

        self._add_agent_config_id.setEnabled(has_choices)
        self._add_agent_btn.setEnabled(bool(str(self._add_agent_config_id.currentData() or "").strip()))

    def _on_test_chain(self) -> None:
        config_cli_map = self._load_config_cli_map()
        agent_names = [
            agent_cli for inst in self._rows if (agent_cli := str(config_cli_map.get(inst.config_id, "") or "").strip())
        ]
        if not agent_names:
            QMessageBox.information(
                self,
                "No agents configured",
                "Add at least one agent with a saved config to test the chain.",
            )
            return

        dialog = TestChainDialog(agent_names, cooldown_manager=None, parent=self)
        dialog.exec()

    def _priority_widget(self, row_index: int) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(4, 1, 4, 1)
        layout.setSpacing(2)

        btn_size = QSize(28, 26)
        icon_size = QSize(18, 18)

        up_btn = QToolButton()
        up_btn.setIcon(lucide_icon("arrow-up", size=18))
        up_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        up_btn.setFixedSize(btn_size)
        up_btn.setIconSize(icon_size)
        up_btn.setStyleSheet("padding: 0px;")
        up_btn.setEnabled(row_index > 0)
        up_btn.setToolTip("Move up (higher priority)")
        up_btn.clicked.connect(lambda: self._move_row(row_index, -1))

        down_btn = QToolButton()
        down_btn.setIcon(lucide_icon("arrow-down", size=18))
        down_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        down_btn.setFixedSize(btn_size)
        down_btn.setIconSize(icon_size)
        down_btn.setStyleSheet("padding: 0px;")
        down_btn.setEnabled(row_index < len(self._rows) - 1)
        down_btn.setToolTip("Move down (lower priority)")
        down_btn.clicked.connect(lambda: self._move_row(row_index, 1))

        layout.addStretch(1)
        layout.addWidget(up_btn, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(down_btn, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch(1)
        return w

    def _move_row(self, row_index: int, delta: int) -> None:
        new_index = row_index + int(delta)
        if row_index < 0 or new_index < 0 or row_index >= len(self._rows) or new_index >= len(self._rows):
            return
        self._rows[row_index], self._rows[new_index] = (
            self._rows[new_index],
            self._rows[row_index],
        )
        self._render_table()
        self._emit_agents_changed()

    def _config_id_widget(
        self,
        row_index: int,
        inst: AgentInstance,
        config_options: list[tuple[str, str]],
    ) -> QWidget:
        current_config_id = str(inst.config_id or "").strip()
        used_elsewhere = self._config_ids_in_use(exclude_row=row_index)

        combo = QComboBox()
        combo.addItem("—", "")
        for config_id, _agent_cli in config_options:
            if config_id in used_elsewhere and config_id != current_config_id:
                continue
            combo.addItem(self._config_combo_label(config_id), config_id)

        if current_config_id and combo.findData(current_config_id) < 0:
            combo.addItem(
                self._config_combo_label(current_config_id, missing=True),
                current_config_id,
            )

        idx = combo.findData(current_config_id)
        combo.setCurrentIndex(idx if idx >= 0 else 0)

        def _on_index_changed(_index: int, *, row: int = row_index) -> None:
            self._commit_row_config_id(row, combo)

        combo.currentIndexChanged.connect(_on_index_changed)
        return combo

    def _commit_row_config_id(self, row_index: int, combo: QComboBox) -> None:
        self._sync_row_config_id(
            row_index,
            str(combo.currentData() or "").strip(),
            emit_signal=True,
            rerender=True,
        )

    def _remap_agent_references(self, old_id: str, new_id: str) -> None:
        if not old_id or not new_id or old_id == new_id:
            return

        updated_fallbacks: dict[str, str] = {}
        for source_id, fallback_id in self._fallbacks.items():
            mapped_source = new_id if source_id == old_id else source_id
            mapped_fallback = new_id if fallback_id == old_id else fallback_id
            if mapped_source and mapped_fallback and mapped_source != mapped_fallback:
                updated_fallbacks[mapped_source] = mapped_fallback
        self._fallbacks = updated_fallbacks

        if old_id in self._cross_agent_allowlist:
            self._cross_agent_allowlist.discard(old_id)
            self._cross_agent_allowlist.add(new_id)

        if self._pinned_agent_id == old_id:
            self._pinned_agent_id = new_id

    def _sync_row_config_id(
        self,
        row_index: int,
        config_id: str,
        *,
        emit_signal: bool,
        rerender: bool,
    ) -> bool:
        if row_index < 0 or row_index >= len(self._rows):
            return False

        current = self._rows[row_index]
        next_config_id = str(config_id or "").strip()
        if next_config_id and next_config_id in self._config_ids_in_use(exclude_row=row_index):
            if rerender:
                QMessageBox.warning(
                    self,
                    "Duplicate config",
                    f"Config ID '{next_config_id}' is already used in this environment.",
                )
                self._render_table()
            return False

        if next_config_id:
            next_agent_id = self._generate_agent_id(next_config_id, exclude_row=row_index)
        else:
            next_agent_id = str(current.agent_id or "").strip() or self._generate_agent_id(
                "agent",
                exclude_row=row_index,
            )

        if next_config_id == current.config_id and next_agent_id == current.agent_id:
            return False

        self._remap_agent_references(current.agent_id, next_agent_id)
        self._rows[row_index] = AgentInstance(
            agent_id=next_agent_id,
            config_id=next_config_id,
        )

        if rerender:
            self._render_table()
        if emit_signal:
            self._emit_agents_changed()
        return True

    def _fallback_widget(self, row_index: int) -> QWidget:
        combo = QComboBox()
        combo.addItem("—", "")

        def _on_index_changed(_index: int, *, row: int = row_index) -> None:
            self._commit_row_fallback(row, combo)

        combo.currentIndexChanged.connect(_on_index_changed)
        return combo

    def _commit_row_fallback(self, row_index: int, combo: QComboBox) -> None:
        self._sync_row_fallback(
            row_index,
            str(combo.currentData() or "").strip(),
            emit_signal=True,
        )

    def _sync_row_fallback(
        self,
        row_index: int,
        fallback_id: str,
        *,
        emit_signal: bool,
    ) -> bool:
        if row_index < 0 or row_index >= len(self._rows):
            return False

        inst = self._rows[row_index]
        current_value = str(self._fallbacks.get(inst.agent_id, "") or "").strip()
        next_value = str(fallback_id or "").strip()

        valid_ids = {row.agent_id for row in self._rows if row.agent_id != inst.agent_id}
        if next_value and next_value not in valid_ids:
            next_value = ""

        if current_value == next_value:
            return False

        if next_value:
            self._fallbacks[inst.agent_id] = next_value
        else:
            self._fallbacks.pop(inst.agent_id, None)

        if emit_signal:
            self._emit_agents_changed()
        return True

    def _cross_agent_widget(self, inst: AgentInstance) -> QWidget:
        w = QWidget()
        layout = QHBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        checkbox = QCheckBox()
        checkbox.setToolTip("Allow this config to be used as a cross-agent (one per CLI)")
        checkbox.blockSignals(True)
        checkbox.setChecked(inst.agent_id in self._cross_agent_allowlist)
        checkbox.blockSignals(False)

        def _on_state_changed(state: int, *, agent_id: str = inst.agent_id) -> None:
            self._on_allowlist_checkbox_changed(agent_id, state)

        checkbox.stateChanged.connect(_on_state_changed)
        self._allowlist_checkboxes[inst.agent_id] = checkbox

        layout.addStretch(1)
        layout.addWidget(checkbox)
        layout.addStretch(1)
        return w

    def _remove_widget(self, row_index: int) -> QWidget:
        btn = QToolButton()
        btn.setObjectName("RowTrash")
        btn.setText("✕")
        btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        btn.clicked.connect(lambda: self._remove_row(row_index))
        return btn

    def _remove_row(self, row_index: int) -> None:
        if row_index < 0 or row_index >= len(self._rows):
            return

        removed_id = self._rows[row_index].agent_id
        self._rows.pop(row_index)
        self._fallbacks.pop(removed_id, None)
        if self._pinned_agent_id == removed_id:
            self._pinned_agent_id = ""

        for source_id, fallback_id in list(self._fallbacks.items()):
            if fallback_id == removed_id:
                self._fallbacks.pop(source_id, None)

        self._cross_agent_allowlist.discard(removed_id)

        self._render_table()
        self._emit_agents_changed()

    def _update_pinned_options(self) -> None:
        ids = [a.agent_id for a in self._rows]
        pinned = str(self._pinned_agent_id or "").strip()
        if pinned not in ids:
            pinned = ""

        self._pinned_agent.blockSignals(True)
        try:
            self._pinned_agent.clear()
            for inst in self._rows:
                self._pinned_agent.addItem(
                    self._row_display_label(inst),
                    inst.agent_id,
                )
            if not pinned and ids and str(self._selection_mode.currentData() or "") == "pinned":
                pinned = ids[0]
            if pinned:
                idx = self._pinned_agent.findData(pinned)
                if idx >= 0:
                    self._pinned_agent.setCurrentIndex(idx)
        finally:
            self._pinned_agent.blockSignals(False)

        self._pinned_agent_id = pinned
        self._pinned_agent.setEnabled(bool(self._rows))

    def _on_pinned_agent_changed(self, _index: int) -> None:
        pinned = str(self._pinned_agent.currentData() or "").strip()
        if pinned == self._pinned_agent_id:
            return
        self._pinned_agent_id = pinned
        self._emit_agents_changed()

    def _update_fallback_options(self) -> None:
        ids = {a.agent_id for a in self._rows}
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
                combo.addItem(self._row_display_label(other), other.agent_id)
            if current_value and current_value in ids:
                idx = combo.findData(current_value)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
            combo.blockSignals(False)

    def flush_widget_state(self) -> None:
        for row_index in range(len(self._rows)):
            config_widget = self._agent_table.cellWidget(row_index, self._COL_CONFIG_ID)
            if isinstance(config_widget, QComboBox):
                self._sync_row_config_id(
                    row_index,
                    str(config_widget.currentData() or "").strip(),
                    emit_signal=False,
                    rerender=False,
                )

        self._update_fallback_options()
        self._update_pinned_options()
        self._refresh_add_agent_options()
        if self._cross_agents_enabled:
            self._update_allowlist_validation()

        for row_index in range(len(self._rows)):
            fallback_widget = self._agent_table.cellWidget(row_index, self._COL_FALLBACK)
            if isinstance(fallback_widget, QComboBox):
                self._sync_row_fallback(
                    row_index,
                    str(fallback_widget.currentData() or "").strip(),
                    emit_signal=False,
                )

        self._update_fallback_options()
        self._update_pinned_options()
        self._refresh_add_agent_options()
        if self._cross_agents_enabled:
            self._update_allowlist_validation()

    def _normalized_rows(self, agents: list[AgentInstance]) -> tuple[list[AgentInstance], dict[str, str]]:
        rows: list[AgentInstance] = []
        remapped_ids: dict[str, str] = {}
        seen_ids: set[str] = set()
        config_id_to_agent_id: dict[str, str] = {}

        for row_index, agent in enumerate(agents):
            raw_agent_id = str(getattr(agent, "agent_id", "") or "").strip()
            config_id = str(getattr(agent, "config_id", "") or "").strip()
            if config_id and config_id in config_id_to_agent_id:
                if raw_agent_id:
                    remapped_ids[raw_agent_id] = config_id_to_agent_id[config_id]
                continue
            base = config_id or raw_agent_id or f"agent-{row_index + 1}"
            agent_id = self._next_unique_agent_id(base, seen_ids)

            rows.append(AgentInstance(agent_id=agent_id, config_id=config_id))
            if config_id:
                config_id_to_agent_id[config_id] = agent_id
            if raw_agent_id:
                remapped_ids[raw_agent_id] = agent_id
            remapped_ids.setdefault(agent_id, agent_id)

        return rows, remapped_ids

    @staticmethod
    def _remap_id(
        value: str,
        remapped_ids: dict[str, str],
        known_ids: set[str],
    ) -> str:
        candidate = remapped_ids.get(str(value or "").strip(), str(value or "").strip())
        return candidate if candidate in known_ids else ""

    def set_agent_selection(self, agent_selection: AgentSelection | None) -> None:
        self._selection_mode.blockSignals(True)
        try:
            if agent_selection is None:
                self._rows = []
                self._fallbacks = {}
                self._pinned_agent_id = ""
                self._cross_agent_allowlist = set()
                self._selection_mode.setCurrentIndex(0)
            else:
                self._rows, remapped_ids = self._normalized_rows(list(agent_selection.agents or []))
                known_ids = {row.agent_id for row in self._rows}

                incoming_fallbacks = dict(agent_selection.agent_fallbacks or {})
                cleaned_fallbacks: dict[str, str] = {}
                for source_id, fallback_id in incoming_fallbacks.items():
                    mapped_source = self._remap_id(source_id, remapped_ids, known_ids)
                    mapped_fallback = self._remap_id(
                        fallback_id,
                        remapped_ids,
                        known_ids,
                    )
                    if mapped_source and mapped_fallback and mapped_source != mapped_fallback:
                        cleaned_fallbacks[mapped_source] = mapped_fallback

                self._fallbacks = cleaned_fallbacks
                self._pinned_agent_id = self._remap_id(
                    str(getattr(agent_selection, "pinned_agent_id", "") or "").strip(),
                    remapped_ids,
                    known_ids,
                )
                self._cross_agent_allowlist = {
                    mapped_id
                    for allowlist_id in self._cross_agent_allowlist
                    if (
                        mapped_id := self._remap_id(
                            allowlist_id,
                            remapped_ids,
                            known_ids,
                        )
                    )
                }

                idx = self._selection_mode.findData(str(agent_selection.selection_mode or "round-robin"))
                self._selection_mode.setCurrentIndex(idx if idx >= 0 else 0)
        finally:
            self._selection_mode.blockSignals(False)

        self._render_table()
        self._refresh_fallback_visibility()
        self._refresh_pinned_visibility()
        self._refresh_priority_visibility()
        self._ensure_pinned_default()

    def get_agent_selection(self) -> AgentSelection | None:
        agents: list[AgentInstance] = []
        seen_ids: set[str] = set()
        for inst in self._rows:
            agent_id = str(inst.agent_id or "").strip()
            config_id = str(inst.config_id or "").strip()
            if not agent_id or agent_id in seen_ids:
                continue
            if config_id and any(agent.config_id == config_id for agent in agents):
                continue
            agents.append(AgentInstance(agent_id=agent_id, config_id=config_id))
            seen_ids.add(agent_id)

        if not agents:
            return None

        known_ids = {agent.agent_id for agent in agents}
        cleaned_fallbacks: dict[str, str] = {}
        for source_id, fallback_id in (self._fallbacks or {}).items():
            mapped_source = str(source_id or "").strip()
            mapped_fallback = str(fallback_id or "").strip()
            if mapped_source in known_ids and mapped_fallback in known_ids and mapped_source != mapped_fallback:
                cleaned_fallbacks[mapped_source] = mapped_fallback

        mode = str(self._selection_mode.currentData() or "round-robin")
        pinned_id = str(self._pinned_agent_id or "").strip()
        if mode == "pinned" and pinned_id not in known_ids:
            pinned_id = agents[0].agent_id if agents else ""

        return AgentSelection(
            agents=agents,
            selection_mode=mode,
            agent_fallbacks=cleaned_fallbacks,
            pinned_agent_id=pinned_id,
        )

    def set_cross_agents_enabled(self, enabled: bool) -> None:
        self._cross_agents_enabled = enabled
        self._refresh_cross_agent_visibility()
        if enabled:
            self._update_allowlist_validation()

    def set_cross_agent_allowlist(self, allowlist: list[str]) -> None:
        self._cross_agent_allowlist = {
            str(agent_id or "").strip() for agent_id in (allowlist or []) if str(agent_id or "").strip()
        }
        for inst in self._rows:
            checkbox = self._allowlist_checkboxes.get(inst.agent_id)
            if checkbox is None:
                continue
            checkbox.blockSignals(True)
            checkbox.setChecked(inst.agent_id in self._cross_agent_allowlist)
            checkbox.blockSignals(False)
        if self._cross_agents_enabled:
            self._update_allowlist_validation()

    def get_cross_agent_allowlist(self) -> list[str]:
        known_ids = {a.agent_id for a in self._rows}
        return [agent_id for agent_id in sorted(self._cross_agent_allowlist) if agent_id in known_ids]

    def _on_allowlist_checkbox_changed(self, agent_id: str, state: int) -> None:
        is_checked = state == Qt.CheckState.Checked.value
        if is_checked:
            self._cross_agent_allowlist.add(agent_id)
        else:
            self._cross_agent_allowlist.discard(agent_id)

        self._update_allowlist_validation()
        self._emit_agents_changed()

    def _cross_agent_cli_key(
        self,
        inst: AgentInstance,
        config_cli_map: dict[str, str],
    ) -> str:
        agent_cli = str(config_cli_map.get(inst.config_id, "") or "").strip().lower()
        return agent_cli or f"__missing__:{inst.agent_id}"

    def _update_allowlist_validation(self) -> None:
        config_cli_map = self._load_config_cli_map()
        cli_to_checked: dict[str, list[str]] = {}
        for inst in self._rows:
            cli_key = self._cross_agent_cli_key(inst, config_cli_map)
            if inst.agent_id in self._cross_agent_allowlist:
                cli_to_checked.setdefault(cli_key, []).append(inst.agent_id)

        for inst in self._rows:
            checkbox = self._allowlist_checkboxes.get(inst.agent_id)
            if checkbox is None:
                continue

            cli_key = self._cross_agent_cli_key(inst, config_cli_map)
            checked_for_cli = cli_to_checked.get(cli_key, [])
            if inst.agent_id in self._cross_agent_allowlist:
                checkbox.setEnabled(True)
            elif checked_for_cli:
                checkbox.setEnabled(False)
            else:
                checkbox.setEnabled(True)
