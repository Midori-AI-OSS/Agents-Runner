from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtCore import Signal
from PySide6.QtGui import QIntValidator
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

from agents_runner.environments import parse_ports_text
from agents_runner.ui.constants import (
    TAB_CONTENT_MARGINS,
    TAB_CONTENT_SPACING,
    BUTTON_ROW_SPACING,
    TABLE_ROW_HEIGHT,
)


_PORT_MIN = 1
_PORT_MAX = 65535
_LOCAL_BIND = "127.0.0.1"
_DESKTOP_CONTAINER_PORT = 6080


@dataclass
class _PortRow:
    host_port: str = ""
    container_port: str = ""


def _publishes_container_port(spec: str, port: int) -> bool:
    base = str(spec or "").strip()
    if not base:
        return False
    base = base.split("/", 1)[0]
    container_part = base.rsplit(":", 1)[-1].strip()
    if not container_part:
        return False
    if container_part.isdigit():
        return int(container_part) == int(port)
    if "-" in container_part:
        left, right = (p.strip() for p in container_part.split("-", 1))
        if left.isdigit() and right.isdigit():
            start = int(left)
            end = int(right)
            p = int(port)
            return start <= p <= end
    return False


def _simple_row_from_spec(spec: str) -> _PortRow | None:
    raw = str(spec or "").strip()
    if not raw:
        return None
    if "/" in raw:
        return None

    parts = raw.split(":")
    if len(parts) == 3:
        ip, host, container = parts
        if ip.strip() != _LOCAL_BIND:
            return None
        if not container.strip().isdigit():
            return None
        if host.strip() and not host.strip().isdigit():
            return None
        return _PortRow(
            host_port=str(host or "").strip(), container_port=container.strip()
        )

    if len(parts) == 2:
        host, container = parts
        if not container.strip().isdigit():
            return None
        if host.strip() and not host.strip().isdigit():
            return None
        return _PortRow(
            host_port=str(host or "").strip(), container_port=container.strip()
        )

    if len(parts) == 1:
        (container,) = parts
        if not container.strip().isdigit():
            return None
        return _PortRow(host_port="", container_port=container.strip())

    return None


class PortsTabWidget(QWidget):
    ports_changed = Signal()

    _COL_HOST = 0
    _COL_CONTAINER = 1
    _COL_REMOVE = 2

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._desktop_effective_enabled: bool = False
        self._unlocked: bool = False
        self._rows: list[_PortRow] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(*TAB_CONTENT_MARGINS)
        layout.setSpacing(TAB_CONTENT_SPACING)

        header_label = QLabel(
            "Simple mode binds ports to 127.0.0.1 only.\n"
            "Leave Host port blank to pick a random free port."
        )
        header_label.setStyleSheet("color: rgba(237, 239, 245, 160);")
        layout.addWidget(header_label)

        unlock_row = QHBoxLayout()
        unlock_row.setSpacing(BUTTON_ROW_SPACING)
        self._unlock_btn = QToolButton()
        self._unlock_btn.setText("Unlock Advanced Ports")
        self._unlock_btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self._unlock_btn.clicked.connect(self._on_unlock_clicked)
        unlock_row.addWidget(self._unlock_btn)
        unlock_row.addStretch(1)
        layout.addLayout(unlock_row)

        self._lock_label = QLabel("Advanced ports are locked.")
        self._lock_label.setStyleSheet("color: rgba(237, 239, 245, 160);")
        layout.addWidget(self._lock_label)

        self._stack = QStackedWidget()
        layout.addWidget(self._stack, 1)

        self._simple_view = QWidget()
        simple_layout = QVBoxLayout(self._simple_view)
        simple_layout.setContentsMargins(0, 0, 0, 0)
        simple_layout.setSpacing(TAB_CONTENT_SPACING)

        self._table = QTableWidget()
        self._table.setColumnCount(3)
        self._table.setHorizontalHeaderLabels(["Host port", "Container port", ""])
        self._table.horizontalHeader().setSectionResizeMode(
            self._COL_HOST, QHeaderView.Stretch
        )
        self._table.horizontalHeader().setSectionResizeMode(
            self._COL_CONTAINER, QHeaderView.Stretch
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

        controls_container = QWidget(self._simple_view)
        controls_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        controls_row = QHBoxLayout(controls_container)
        controls_row.setContentsMargins(0, 0, 0, 0)
        controls_row.setSpacing(BUTTON_ROW_SPACING)

        controls_row.addWidget(QLabel("Add port"))
        add_btn = QToolButton()
        add_btn.setText("Add")
        add_btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
        add_btn.clicked.connect(self._on_add_row)
        controls_row.addWidget(add_btn)
        controls_row.addStretch(1)
        simple_layout.addWidget(controls_container, 0)

        self._advanced_view = QWidget()
        advanced_layout = QVBoxLayout(self._advanced_view)
        advanced_layout.setContentsMargins(0, 0, 0, 0)
        advanced_layout.setSpacing(TAB_CONTENT_SPACING)

        self._advanced_text = QPlainTextEdit()
        self._advanced_text.setPlaceholderText(
            "\n".join(
                [
                    "# docker -p values (one per line)",
                    "# 127.0.0.1:3000:3000",
                    "# 127.0.0.1::3000  # random host port",
                    "",
                ]
            )
        )
        self._advanced_text.setTabChangesFocus(True)
        self._advanced_text.textChanged.connect(self.ports_changed.emit)
        advanced_layout.addWidget(QLabel("Port forwards"))
        advanced_layout.addWidget(self._advanced_text, 1)

        self._stack.addWidget(self._simple_view)
        self._stack.addWidget(self._advanced_view)
        self._stack.setCurrentIndex(0)

        self._render_table()
        self._sync_lock_state()

    def set_desktop_effective_enabled(self, enabled: bool) -> None:
        self._desktop_effective_enabled = bool(enabled)

    def set_ports(self, ports: list[str], unlocked: bool) -> None:
        raw_ports = [
            str(p or "").strip() for p in (ports or []) if str(p or "").strip()
        ]
        wants_unlocked = bool(unlocked)

        rows: list[_PortRow] = []
        for spec in raw_ports:
            row = _simple_row_from_spec(spec)
            if row is None:
                wants_unlocked = True
                continue
            rows.append(row)

        self._rows = rows
        self._unlocked = wants_unlocked

        if self._unlocked:
            self._advanced_text.blockSignals(True)
            try:
                self._advanced_text.setPlainText("\n".join(raw_ports))
            finally:
                self._advanced_text.blockSignals(False)
        else:
            self._advanced_text.blockSignals(True)
            try:
                self._advanced_text.setPlainText("")
            finally:
                self._advanced_text.blockSignals(False)

        self._render_table()
        self._sync_lock_state()

    def get_ports(self) -> tuple[list[str], bool, list[str]]:
        if self._unlocked:
            ports, errors = parse_ports_text(self._advanced_text.toPlainText() or "")
            if self._desktop_effective_enabled:
                for idx, spec in enumerate(ports, start=1):
                    if _publishes_container_port(spec, _DESKTOP_CONTAINER_PORT):
                        errors.append(
                            f"line {idx}: container port {_DESKTOP_CONTAINER_PORT} is reserved when desktop is enabled"
                        )
            return ports, True, errors

        ports: list[str] = []
        errors: list[str] = []
        for row_index, row in enumerate(self._rows, start=1):
            host_text = str(row.host_port or "").strip()
            container_text = str(row.container_port or "").strip()

            if not host_text and not container_text:
                continue
            if not container_text:
                errors.append(f"row {row_index}: missing container port")
                continue
            if not container_text.isdigit():
                errors.append(f"row {row_index}: invalid container port")
                continue
            container_port = int(container_text)
            if not (_PORT_MIN <= container_port <= _PORT_MAX):
                errors.append(f"row {row_index}: container port out of range")
                continue
            if (
                self._desktop_effective_enabled
                and container_port == _DESKTOP_CONTAINER_PORT
            ):
                errors.append(
                    f"row {row_index}: container port {_DESKTOP_CONTAINER_PORT} is reserved when desktop is enabled"
                )
                continue

            if host_text:
                if not host_text.isdigit():
                    errors.append(f"row {row_index}: invalid host port")
                    continue
                host_port = int(host_text)
                if not (_PORT_MIN <= host_port <= _PORT_MAX):
                    errors.append(f"row {row_index}: host port out of range")
                    continue
                ports.append(f"{_LOCAL_BIND}:{host_port}:{container_port}")
            else:
                ports.append(f"{_LOCAL_BIND}::{container_port}")

        return ports, False, errors

    def _on_unlock_clicked(self) -> None:
        if self._unlocked:
            return

        result = QMessageBox.warning(
            self,
            "Warning: Unlock Advanced Ports",
            "Advanced port publishing accepts raw docker -p values.\n\n"
            "Invalid publishes can break tasks or expose services unintentionally.\n\n"
            "Do you want to proceed?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if result != QMessageBox.Yes:
            return

        ports, _unlocked, _errors = self.get_ports()
        self._unlocked = True
        self._advanced_text.setPlainText("\n".join(ports))
        self._sync_lock_state()
        self.ports_changed.emit()

    def _on_add_row(self) -> None:
        self._rows.append(_PortRow(host_port="", container_port=""))
        self._render_table()
        self.ports_changed.emit()

    def _sync_lock_state(self) -> None:
        if self._unlocked:
            self._unlock_btn.setVisible(False)
            self._lock_label.setVisible(False)
            self._stack.setCurrentIndex(1)
        else:
            self._unlock_btn.setVisible(True)
            self._lock_label.setVisible(True)
            self._stack.setCurrentIndex(0)

    def _render_table(self) -> None:
        self._table.setRowCount(len(self._rows))
        self._table.setMinimumHeight(1)

        validator = QIntValidator(_PORT_MIN, _PORT_MAX, self)

        for row_index, row in enumerate(self._rows):
            self._table.setRowHeight(row_index, TABLE_ROW_HEIGHT)

            host = QLineEdit()
            host.setPlaceholderText("random")
            host.setText(str(row.host_port or ""))
            host.setValidator(validator)
            host.editingFinished.connect(
                lambda r=row_index, w=host: self._commit_host_port(r, w)
            )
            self._table.setCellWidget(row_index, self._COL_HOST, host)

            container = QLineEdit()
            container.setPlaceholderText("container")
            container.setText(str(row.container_port or ""))
            container.setValidator(validator)
            container.editingFinished.connect(
                lambda r=row_index, w=container: self._commit_container_port(r, w)
            )
            self._table.setCellWidget(row_index, self._COL_CONTAINER, container)

            remove_btn = QToolButton()
            remove_btn.setObjectName("RowTrash")
            remove_btn.setText("✕")
            remove_btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
            remove_btn.clicked.connect(lambda r=row_index: self._remove_row(r))
            self._table.setCellWidget(row_index, self._COL_REMOVE, remove_btn)

    def _commit_host_port(self, row_index: int, widget: QLineEdit) -> None:
        if row_index < 0 or row_index >= len(self._rows):
            return
        self._rows[row_index].host_port = str(widget.text() or "").strip()
        self.ports_changed.emit()

    def _commit_container_port(self, row_index: int, widget: QLineEdit) -> None:
        if row_index < 0 or row_index >= len(self._rows):
            return
        self._rows[row_index].container_port = str(widget.text() or "").strip()
        self.ports_changed.emit()

    def _remove_row(self, row_index: int) -> None:
        if row_index < 0 or row_index >= len(self._rows):
            return
        self._rows.pop(row_index)
        self._render_table()
        self.ports_changed.emit()
