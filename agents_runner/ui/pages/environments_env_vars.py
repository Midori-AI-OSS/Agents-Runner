from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout
from PySide6.QtWidgets import QHeaderView
from PySide6.QtWidgets import QLabel
from PySide6.QtWidgets import QLineEdit
from PySide6.QtWidgets import QMessageBox
from PySide6.QtWidgets import QPlainTextEdit
from PySide6.QtWidgets import QSizePolicy
from PySide6.QtWidgets import QStackedWidget
from PySide6.QtWidgets import QTableWidget
from PySide6.QtWidgets import QToolButton
from PySide6.QtWidgets import QVBoxLayout
from PySide6.QtWidgets import QWidget

from agents_runner.environments import parse_env_vars_text
from agents_runner.ui.lucide_icons import lucide_icon
from agents_runner.ui.constants import (
    BUTTON_ROW_SPACING,
    TAB_CONTENT_MARGINS,
    TAB_CONTENT_SPACING,
    TABLE_ROW_HEIGHT,
)


@dataclass
class _EnvVarRow:
    key: str = ""
    value: str = ""


class EnvVarsTabWidget(QWidget):
    env_vars_changed = Signal()

    _COL_KEY = 0
    _COL_VALUE = 1
    _COL_REMOVE = 2

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._rows: list[_EnvVarRow] = []
        self._advanced_mode = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(*TAB_CONTENT_MARGINS)
        layout.setSpacing(TAB_CONTENT_SPACING)

        self._stack = QStackedWidget()
        layout.addWidget(self._stack, 1)

        self._simple_view = QWidget()
        simple_layout = QVBoxLayout(self._simple_view)
        simple_layout.setContentsMargins(0, 0, 0, 0)
        simple_layout.setSpacing(TAB_CONTENT_SPACING)

        self._table = QTableWidget()
        self._table.setColumnCount(3)
        self._table.setHorizontalHeaderLabels(["Key", "Value", ""])
        self._table.horizontalHeader().setSectionResizeMode(
            self._COL_KEY, QHeaderView.Stretch
        )
        self._table.horizontalHeader().setSectionResizeMode(
            self._COL_VALUE, QHeaderView.Stretch
        )
        self._table.horizontalHeader().setSectionResizeMode(
            self._COL_REMOVE, QHeaderView.ResizeToContents
        )
        self._table.verticalHeader().setVisible(False)
        self._table.verticalHeader().setMinimumSectionSize(TABLE_ROW_HEIGHT)
        self._table.verticalHeader().setDefaultSectionSize(TABLE_ROW_HEIGHT)
        self._table.setSelectionMode(QTableWidget.NoSelection)
        self._table.setFocusPolicy(Qt.NoFocus)
        self._table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        simple_layout.addWidget(self._table, 1)

        self._advanced_view = QWidget()
        advanced_layout = QVBoxLayout(self._advanced_view)
        advanced_layout.setContentsMargins(0, 0, 0, 0)
        advanced_layout.setSpacing(TAB_CONTENT_SPACING)

        self._advanced_text = QPlainTextEdit()
        self._advanced_text.setPlaceholderText(
            "\n".join(
                [
                    "# KEY=VALUE (one per line)",
                    "# EXAMPLE_KEY=example value",
                    "",
                ]
            )
        )
        self._advanced_text.setTabChangesFocus(True)
        self._advanced_text.textChanged.connect(self.env_vars_changed.emit)
        advanced_layout.addWidget(QLabel("Environment variables"))
        advanced_layout.addWidget(self._advanced_text, 1)

        self._stack.addWidget(self._simple_view)
        self._stack.addWidget(self._advanced_view)
        self._stack.setCurrentIndex(0)

        footer_row = QHBoxLayout()
        footer_row.setSpacing(BUTTON_ROW_SPACING)
        self._add_label = QLabel("Add variable")
        footer_row.addWidget(self._add_label)
        self._add_btn = QToolButton()
        self._add_btn.setText("Add")
        self._add_btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self._add_btn.clicked.connect(self._on_add_row)
        footer_row.addWidget(self._add_btn)
        footer_row.addStretch(1)
        self._mode_btn = QToolButton()
        self._mode_btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self._mode_btn.clicked.connect(self._on_mode_clicked)
        footer_row.addWidget(self._mode_btn)
        layout.addLayout(footer_row)

        self._render_table()
        self._sync_mode_state()

    def set_env_vars(self, env_vars: dict[str, str]) -> None:
        self._rows = [
            _EnvVarRow(key=str(key or "").strip(), value=str(value or ""))
            for key, value in sorted((env_vars or {}).items(), key=lambda item: item[0])
            if str(key or "").strip()
        ]
        self._advanced_mode = False

        self._advanced_text.blockSignals(True)
        try:
            lines = [f"{row.key}={row.value}" for row in self._rows]
            self._advanced_text.setPlainText("\n".join(lines))
        finally:
            self._advanced_text.blockSignals(False)

        self._render_table()
        self._sync_mode_state()

    def get_env_vars(self) -> tuple[dict[str, str], list[str]]:
        if self._advanced_mode:
            return parse_env_vars_text(self._advanced_text.toPlainText() or "")

        parsed: dict[str, str] = {}
        errors: list[str] = []
        for row_index, row in enumerate(self._rows, start=1):
            key = str(row.key or "").strip()
            value = str(row.value or "")
            if not key and not value:
                continue
            if not key:
                errors.append(f"row {row_index}: empty key")
                continue
            parsed[key] = value
        return parsed, errors

    def _on_mode_clicked(self) -> None:
        if self._advanced_mode:
            self._switch_to_simple_mode()
            return
        self._switch_to_advanced_mode()

    def _on_add_row(self) -> None:
        self._rows.append(_EnvVarRow(key="", value=""))
        self._render_table()
        self.env_vars_changed.emit()

    def _sync_mode_state(self) -> None:
        if self._advanced_mode:
            self._stack.setCurrentIndex(1)
            self._mode_btn.setText("Simple Mode")
            self._add_label.setVisible(False)
            self._add_btn.setVisible(False)
            return
        self._stack.setCurrentIndex(0)
        self._mode_btn.setText("Advanced Mode")
        self._add_label.setVisible(True)
        self._add_btn.setVisible(True)

    def _switch_to_advanced_mode(self) -> None:
        lines: list[str] = []
        for row in self._rows:
            key = str(row.key or "").strip()
            value = str(row.value or "")
            if not key and not value:
                continue
            lines.append(f"{key}={value}")
        self._advanced_text.blockSignals(True)
        try:
            self._advanced_text.setPlainText("\n".join(lines))
        finally:
            self._advanced_text.blockSignals(False)
        self._advanced_mode = True
        self._sync_mode_state()
        self.env_vars_changed.emit()

    def _switch_to_simple_mode(self) -> None:
        parsed, errors = parse_env_vars_text(self._advanced_text.toPlainText() or "")
        if errors:
            QMessageBox.warning(
                self,
                "Invalid environment variables",
                "Fix entries before leaving Advanced mode:\n" + "\n".join(errors[:12]),
            )
            return
        self._rows = [
            _EnvVarRow(key=str(key or "").strip(), value=str(value or ""))
            for key, value in parsed.items()
            if str(key or "").strip()
        ]
        self._advanced_mode = False
        self._render_table()
        self._sync_mode_state()
        self.env_vars_changed.emit()

    def _render_table(self) -> None:
        self._table.blockSignals(True)
        try:
            self._table.setRowCount(0)
            for row_index, row in enumerate(self._rows):
                self._table.insertRow(row_index)

                key_edit = QLineEdit(str(row.key or ""))
                key_edit.setPlaceholderText("KEY")
                key_edit.textChanged.connect(
                    lambda text, i=row_index: self._on_key_changed(i, text)
                )
                self._table.setCellWidget(row_index, self._COL_KEY, key_edit)

                value_edit = QLineEdit(str(row.value or ""))
                value_edit.setPlaceholderText("Value")
                value_edit.textChanged.connect(
                    lambda text, i=row_index: self._on_value_changed(i, text)
                )
                self._table.setCellWidget(row_index, self._COL_VALUE, value_edit)

                remove_btn = QToolButton()
                remove_btn.setObjectName("RowTrash")
                remove_btn.setIcon(lucide_icon("trash-2"))
                remove_btn.setToolButtonStyle(Qt.ToolButtonIconOnly)
                remove_btn.setToolTip("Remove row")
                remove_btn.clicked.connect(
                    lambda _=False, i=row_index: self._on_remove_row(i)
                )
                self._table.setCellWidget(row_index, self._COL_REMOVE, remove_btn)
        finally:
            self._table.blockSignals(False)

    def _on_key_changed(self, row_index: int, text: str) -> None:
        if row_index >= len(self._rows):
            return
        self._rows[row_index].key = str(text or "")
        self.env_vars_changed.emit()

    def _on_value_changed(self, row_index: int, text: str) -> None:
        if row_index >= len(self._rows):
            return
        self._rows[row_index].value = str(text or "")
        self.env_vars_changed.emit()

    def _on_remove_row(self, row_index: int) -> None:
        if row_index < 0 or row_index >= len(self._rows):
            return
        self._rows.pop(row_index)
        self._render_table()
        self.env_vars_changed.emit()
