from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox
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

from agents_runner.environments import parse_mounts_text
from agents_runner.ui.lucide_icons import lucide_icon
from agents_runner.ui.constants import (
    BUTTON_ROW_SPACING,
    TAB_CONTENT_MARGINS,
    TAB_CONTENT_SPACING,
    TABLE_ROW_HEIGHT,
)


_MOUNT_MODES = ("rw", "ro", "cached", "delegated")


@dataclass
class _MountRow:
    host_path: str = ""
    container_path: str = ""
    mode: str = "rw"


def _simple_mount_row_from_spec(spec: str) -> _MountRow | None:
    text = str(spec or "").strip()
    if not text:
        return None
    parts = text.split(":")
    if len(parts) < 2:
        return None
    host_path = str(parts[0] or "").strip()
    container_path = str(parts[1] or "").strip()
    if not host_path or not container_path:
        return None
    mode = "rw"
    if len(parts) >= 3:
        mode = str(parts[2] or "").strip().lower() or "rw"
    if mode not in _MOUNT_MODES:
        return None
    return _MountRow(host_path=host_path, container_path=container_path, mode=mode)


class MountsTabWidget(QWidget):
    mounts_changed = Signal()

    _COL_HOST_PATH = 0
    _COL_CONTAINER_PATH = 1
    _COL_MODE = 2
    _COL_REMOVE = 3

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._rows: list[_MountRow] = []
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
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(
            ["Host path", "Container path", "Mode", ""]
        )
        self._table.horizontalHeader().setSectionResizeMode(
            self._COL_HOST_PATH, QHeaderView.Stretch
        )
        self._table.horizontalHeader().setSectionResizeMode(
            self._COL_CONTAINER_PATH, QHeaderView.Stretch
        )
        self._table.horizontalHeader().setSectionResizeMode(
            self._COL_MODE, QHeaderView.ResizeToContents
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
                    "# host_path:container_path[:mode]",
                    "# /home/user/.ssh:/home/midori-ai/.ssh:ro",
                    "",
                ]
            )
        )
        self._advanced_text.setTabChangesFocus(True)
        self._advanced_text.textChanged.connect(self.mounts_changed.emit)
        advanced_layout.addWidget(QLabel("Mount definitions"))
        advanced_layout.addWidget(self._advanced_text, 1)

        self._stack.addWidget(self._simple_view)
        self._stack.addWidget(self._advanced_view)
        self._stack.setCurrentIndex(0)

        footer_row = QHBoxLayout()
        footer_row.setSpacing(BUTTON_ROW_SPACING)
        self._add_label = QLabel("Add mount")
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

    def set_mounts(self, mounts: list[str]) -> None:
        parsed_rows: list[_MountRow] = []
        use_advanced_mode = False
        for spec in mounts or []:
            row = _simple_mount_row_from_spec(str(spec or "").strip())
            if row is None:
                use_advanced_mode = True
                continue
            parsed_rows.append(row)

        self._rows = parsed_rows
        self._advanced_mode = use_advanced_mode

        self._advanced_text.blockSignals(True)
        try:
            self._advanced_text.setPlainText(
                "\n".join(
                    str(spec or "").strip()
                    for spec in mounts or []
                    if str(spec or "").strip()
                )
            )
        finally:
            self._advanced_text.blockSignals(False)

        self._render_table()
        self._sync_mode_state()

    def get_mounts(self) -> tuple[list[str], list[str]]:
        if self._advanced_mode:
            mounts = parse_mounts_text(self._advanced_text.toPlainText() or "")
            return mounts, []

        mounts: list[str] = []
        errors: list[str] = []
        for row_index, row in enumerate(self._rows, start=1):
            host_path = str(row.host_path or "").strip()
            container_path = str(row.container_path or "").strip()
            mode = str(row.mode or "rw").strip().lower() or "rw"

            if not host_path and not container_path:
                continue
            if not host_path:
                errors.append(f"row {row_index}: missing host path")
                continue
            if not container_path:
                errors.append(f"row {row_index}: missing container path")
                continue
            if mode not in _MOUNT_MODES:
                errors.append(f"row {row_index}: unsupported mode '{mode}'")
                continue
            mounts.append(f"{host_path}:{container_path}:{mode}")
        return mounts, errors

    def _on_mode_clicked(self) -> None:
        if self._advanced_mode:
            self._switch_to_simple_mode()
            return
        self._switch_to_advanced_mode()

    def _on_add_row(self) -> None:
        self._rows.append(_MountRow())
        self._render_table()
        self.mounts_changed.emit()

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
            host_path = str(row.host_path or "").strip()
            container_path = str(row.container_path or "").strip()
            mode = str(row.mode or "rw").strip().lower() or "rw"
            if not host_path and not container_path:
                continue
            lines.append(f"{host_path}:{container_path}:{mode}")
        self._advanced_text.blockSignals(True)
        try:
            self._advanced_text.setPlainText("\n".join(lines))
        finally:
            self._advanced_text.blockSignals(False)
        self._advanced_mode = True
        self._sync_mode_state()
        self.mounts_changed.emit()

    def _switch_to_simple_mode(self) -> None:
        mounts = parse_mounts_text(self._advanced_text.toPlainText() or "")
        rows: list[_MountRow] = []
        errors: list[str] = []
        for index, spec in enumerate(mounts, start=1):
            row = _simple_mount_row_from_spec(spec)
            if row is None:
                errors.append(
                    f"line {index}: expected host_path:container_path[:rw|ro|cached|delegated]"
                )
                continue
            rows.append(row)

        if errors:
            QMessageBox.warning(
                self,
                "Cannot switch to Simple mode",
                "Fix entries before leaving Advanced mode:\n" + "\n".join(errors[:12]),
            )
            return

        self._rows = rows
        self._advanced_mode = False
        self._render_table()
        self._sync_mode_state()
        self.mounts_changed.emit()

    def _render_table(self) -> None:
        self._table.blockSignals(True)
        try:
            self._table.setRowCount(0)
            for row_index, row in enumerate(self._rows):
                self._table.insertRow(row_index)

                host_edit = QLineEdit(str(row.host_path or ""))
                host_edit.setPlaceholderText("/host/path")
                host_edit.textChanged.connect(
                    lambda text, i=row_index: self._on_host_path_changed(i, text)
                )
                self._table.setCellWidget(row_index, self._COL_HOST_PATH, host_edit)

                container_edit = QLineEdit(str(row.container_path or ""))
                container_edit.setPlaceholderText("/container/path")
                container_edit.textChanged.connect(
                    lambda text, i=row_index: self._on_container_path_changed(i, text)
                )
                self._table.setCellWidget(
                    row_index, self._COL_CONTAINER_PATH, container_edit
                )

                mode_combo = QComboBox()
                for mode in _MOUNT_MODES:
                    mode_combo.addItem(mode, mode)
                mode_index = mode_combo.findData(str(row.mode or "rw").strip().lower())
                if mode_index < 0:
                    mode_index = mode_combo.findData("rw")
                mode_combo.setCurrentIndex(mode_index)
                mode_combo.currentIndexChanged.connect(
                    lambda _idx, i=row_index, combo=mode_combo: self._on_mode_changed(
                        i, combo
                    )
                )
                self._table.setCellWidget(row_index, self._COL_MODE, mode_combo)

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

    def _on_host_path_changed(self, row_index: int, text: str) -> None:
        if row_index >= len(self._rows):
            return
        self._rows[row_index].host_path = str(text or "")
        self.mounts_changed.emit()

    def _on_container_path_changed(self, row_index: int, text: str) -> None:
        if row_index >= len(self._rows):
            return
        self._rows[row_index].container_path = str(text or "")
        self.mounts_changed.emit()

    def _on_mode_changed(self, row_index: int, combo: QComboBox) -> None:
        if row_index >= len(self._rows):
            return
        mode = str(combo.currentData() or "rw").strip().lower() or "rw"
        self._rows[row_index].mode = mode
        self.mounts_changed.emit()

    def _on_remove_row(self, row_index: int) -> None:
        if row_index < 0 or row_index >= len(self._rows):
            return
        self._rows.pop(row_index)
        self._render_table()
        self.mounts_changed.emit()
