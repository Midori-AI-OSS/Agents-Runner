from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHeaderView
from PySide6.QtWidgets import QLabel
from PySide6.QtWidgets import QLineEdit
from PySide6.QtWidgets import QSizePolicy
from PySide6.QtWidgets import QTableWidget
from PySide6.QtWidgets import QToolButton
from PySide6.QtWidgets import QVBoxLayout
from PySide6.QtWidgets import QWidget

from agents_runner.ui.constants import TABLE_ROW_HEIGHT
from agents_runner.ui.lucide_icons import lucide_icon


def _normalize_username(value: object) -> str:
    username = str(value or "").strip().lstrip("@")
    if not username:
        return ""
    # GitHub usernames are case-insensitive; preserve canonical lowercase form.
    return username.lower()


class GitHubUsernameListWidget(QWidget):
    usernames_changed = Signal()

    _COL_USERNAME = 0
    _COL_REMOVE = 1

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._rows: list[str] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._table = QTableWidget()
        self._table.setColumnCount(2)
        self._table.setHorizontalHeaderLabels(["GitHub username", ""])
        self._table.horizontalHeader().setSectionResizeMode(
            self._COL_USERNAME, QHeaderView.Stretch
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
        layout.addWidget(self._table, 1)

        actions = QWidget()
        actions_layout = QVBoxLayout(actions)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(0)
        add_label = QLabel("Add trusted user")
        actions_layout.addWidget(add_label)
        add_btn = QToolButton()
        add_btn.setText("Add")
        add_btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
        add_btn.clicked.connect(self._on_add_row)
        actions_layout.addWidget(add_btn, 0, Qt.AlignLeft)
        layout.addWidget(actions)

        self._render_table()

    def set_usernames(self, usernames: list[str]) -> None:
        cleaned: list[str] = []
        seen: set[str] = set()
        for raw in usernames or []:
            username = _normalize_username(raw)
            if not username or username in seen:
                continue
            cleaned.append(username)
            seen.add(username)
        self._rows = cleaned
        self._render_table()

    def get_usernames(self) -> list[str]:
        cleaned: list[str] = []
        seen: set[str] = set()
        for row in self._rows:
            username = _normalize_username(row)
            if not username or username in seen:
                continue
            cleaned.append(username)
            seen.add(username)
        return cleaned

    def merge_usernames(self, usernames: list[str]) -> None:
        merged = self.get_usernames()
        merged.extend(usernames or [])
        self.set_usernames(merged)
        self.usernames_changed.emit()

    def _on_add_row(self) -> None:
        self._rows.append("")
        self._render_table()
        self.usernames_changed.emit()

    def _render_table(self) -> None:
        self._table.blockSignals(True)
        try:
            self._table.setRowCount(0)
            for row_index, username in enumerate(self._rows):
                self._table.insertRow(row_index)

                username_edit = QLineEdit(username)
                username_edit.setPlaceholderText("username")
                username_edit.textChanged.connect(
                    lambda text, i=row_index: self._on_username_changed(i, text)
                )
                self._table.setCellWidget(row_index, self._COL_USERNAME, username_edit)

                remove_btn = QToolButton()
                remove_btn.setObjectName("RowTrash")
                remove_btn.setIcon(lucide_icon("trash-2"))
                remove_btn.setToolButtonStyle(Qt.ToolButtonIconOnly)
                remove_btn.setToolTip("Remove user")
                remove_btn.clicked.connect(
                    lambda _=False, i=row_index: self._on_remove_row(i)
                )
                self._table.setCellWidget(row_index, self._COL_REMOVE, remove_btn)
        finally:
            self._table.blockSignals(False)

    def _on_username_changed(self, row_index: int, text: str) -> None:
        if row_index >= len(self._rows):
            return
        self._rows[row_index] = _normalize_username(text)
        self.usernames_changed.emit()

    def _on_remove_row(self, row_index: int) -> None:
        if row_index < 0 or row_index >= len(self._rows):
            return
        self._rows.pop(row_index)
        self._render_table()
        self.usernames_changed.emit()
