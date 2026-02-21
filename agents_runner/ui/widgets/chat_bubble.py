from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QPointF
from PySide6.QtCore import Qt
from PySide6.QtCore import Signal
from PySide6.QtGui import QPaintEvent
from PySide6.QtGui import QPainter
from PySide6.QtGui import QPainterPath
from PySide6.QtGui import QPolygonF
from PySide6.QtWidgets import QHBoxLayout
from PySide6.QtWidgets import QLabel
from PySide6.QtWidgets import QSizePolicy
from PySide6.QtWidgets import QToolButton
from PySide6.QtWidgets import QVBoxLayout
from PySide6.QtWidgets import QWidget

from agents_runner.ui.lucide_icons import lucide_icon
from agents_runner.ui.utils import ChatBubbleTone
from agents_runner.ui.utils import resolve_chat_bubble_tone
from agents_runner.ui.utils import rgba


@dataclass(frozen=True)
class ChatBubbleAction:
    action_id: str
    label: str
    icon_name: str = ""
    tooltip: str = ""


@dataclass(frozen=True)
class ChatBubbleData:
    author: str
    timestamp: str
    body: str
    role: str = "other"
    actions: tuple[ChatBubbleAction, ...] = ()


class _BubbleSurface(QWidget):
    _TAIL_WIDTH = 12
    _TAIL_HEIGHT = 8
    _TAIL_INSET = 14

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._tail_side = "left"
        self._tone = resolve_chat_bubble_tone(
            role="other", env_stain="slate", username="unknown"
        )
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

    def set_tail_side(self, side: str) -> None:
        normalized = "right" if str(side or "").strip().lower() == "right" else "left"
        if normalized == self._tail_side:
            return
        self._tail_side = normalized
        self.update()

    def set_tone(self, tone: ChatBubbleTone) -> None:
        self._tone = tone
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        super().paintEvent(event)
        rect = self.rect().adjusted(0, 0, -1, -1)
        if rect.width() <= 0 or rect.height() <= 0:
            return

        body = rect.adjusted(0, 0, 0, -self._TAIL_HEIGHT)
        path = QPainterPath()
        path.addRect(body)

        if self._tail_side == "right":
            tail_start = body.right() - self._TAIL_INSET - self._TAIL_WIDTH
        else:
            tail_start = body.left() + self._TAIL_INSET

        if self._tail_side == "left":
            p1 = QPointF(float(tail_start), float(body.bottom()))
            p2 = QPointF(float(tail_start + self._TAIL_WIDTH), float(body.bottom()))
        else:
            p1 = QPointF(float(tail_start + self._TAIL_WIDTH), float(body.bottom()))
            p2 = QPointF(float(tail_start), float(body.bottom()))
        p3 = QPointF(float(p1.x()), float(body.bottom() + self._TAIL_HEIGHT))

        tail = QPolygonF([p1, p2, p3])
        tail_path = QPainterPath()
        tail_path.addPolygon(tail)
        tail_path.closeSubpath()
        path = path.united(tail_path)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)
        painter.setPen(self._tone.border)
        painter.setBrush(self._tone.fill)
        painter.drawPath(path)


class ChatBubbleWidget(QWidget):
    action_requested = Signal(str)
    reply_requested = Signal()
    open_requested = Signal()
    primary_requested = Signal()

    _MAX_BUBBLE_WIDTH = 720

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._tone = resolve_chat_bubble_tone(
            role="other", env_stain="slate", username="unknown"
        )
        self._flipped = False
        self._action_buttons: dict[str, QToolButton] = {}

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self._root = root

        self._surface = _BubbleSurface()
        self._surface.setMaximumWidth(self._MAX_BUBBLE_WIDTH)
        self._surface.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        content = QVBoxLayout(self._surface)
        content.setContentsMargins(12, 9, 12, 14)
        content.setSpacing(6)
        self._content_layout = content

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)

        self._author = QLabel("unknown")
        self._author.setStyleSheet("font-size: 13px; font-weight: 700;")
        self._author.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self._timestamp = QLabel("")
        self._timestamp.setStyleSheet("font-size: 12px;")
        self._timestamp.setTextInteractionFlags(Qt.TextSelectableByMouse)

        header.addWidget(self._author, 0)
        header.addStretch(1)
        header.addWidget(self._timestamp, 0, Qt.AlignRight)
        self._content_layout.addLayout(header)

        self._body = QLabel("")
        self._body.setWordWrap(True)
        self._body.setTextFormat(Qt.PlainText)
        self._body.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._body.setStyleSheet("font-size: 13px; font-weight: 500;")
        self._content_layout.addWidget(self._body)

        self._actions_row = QWidget()
        self._actions_layout = QHBoxLayout(self._actions_row)
        self._actions_layout.setContentsMargins(0, 2, 0, 0)
        self._actions_layout.setSpacing(6)
        self._actions_layout.addStretch(1)
        self._content_layout.addWidget(self._actions_row)

        self._apply_alignment()
        self._apply_tone()

    def _apply_alignment(self) -> None:
        while self._root.count() > 0:
            item = self._root.takeAt(0)
            widget = item.widget()
            if widget is not None and widget is not self._surface:
                widget.setParent(None)

        if self._flipped:
            self._root.addStretch(1)
            self._root.addWidget(self._surface, 0)
            self._surface.set_tail_side("right")
            self._actions_layout.setAlignment(Qt.AlignRight)
        else:
            self._root.addWidget(self._surface, 0)
            self._root.addStretch(1)
            self._surface.set_tail_side("left")
            self._actions_layout.setAlignment(Qt.AlignLeft)

    def _apply_tone(self) -> None:
        self._surface.set_tone(self._tone)
        self._author.setStyleSheet(
            f"font-size: 13px; font-weight: 700; color: {rgba(self._tone.text_primary)};"
        )
        self._timestamp.setStyleSheet(
            f"font-size: 12px; color: {rgba(self._tone.text_secondary)};"
        )
        self._body.setStyleSheet(
            f"font-size: 13px; font-weight: 500; color: {rgba(self._tone.text_primary)};"
        )
        for button in self._action_buttons.values():
            button.setStyleSheet(
                "\n".join(
                    [
                        "QToolButton {",
                        f"  color: {rgba(self._tone.text_primary)};",
                        f"  background-color: {rgba(self._tone.action_fill)};",
                        f"  border: 1px solid {rgba(self._tone.action_border)};",
                        "  border-radius: 0px;",
                        "  padding: 5px 8px;",
                        "  font-size: 12px;",
                        "  font-weight: 650;",
                        "}",
                        "QToolButton:hover {",
                        f"  background-color: {rgba(self._tone.action_hover_fill)};",
                        f"  border: 1px solid {rgba(self._tone.action_hover_border)};",
                        "}",
                        "QToolButton:pressed {",
                        f"  background-color: {rgba(self._tone.action_hover_fill)};",
                        f"  border: 1px solid {rgba(self._tone.action_hover_border)};",
                        "}",
                    ]
                )
            )

    def _clear_action_buttons(self) -> None:
        while self._actions_layout.count() > 0:
            item = self._actions_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._action_buttons.clear()

    def _emit_action(self, action_id: str) -> None:
        action = str(action_id or "").strip().lower()
        if not action:
            return
        self.action_requested.emit(action)
        if action == "reply":
            self.reply_requested.emit()
        elif action == "open":
            self.open_requested.emit()
        elif action == "primary":
            self.primary_requested.emit()

    def set_tone(self, tone: ChatBubbleTone) -> None:
        self._tone = tone
        self._apply_tone()

    def set_flipped(self, flipped: bool) -> None:
        new_value = bool(flipped)
        if new_value == self._flipped:
            return
        self._flipped = new_value
        self._apply_alignment()

    def set_data(self, data: ChatBubbleData) -> None:
        role = str(data.role or "").strip().lower()
        self.set_flipped(role == "self")
        self._author.setText(str(data.author or "unknown"))
        self._timestamp.setText(str(data.timestamp or ""))
        self._body.setText(str(data.body or ""))

        self._clear_action_buttons()
        if data.actions:
            for action in data.actions:
                action_id = str(action.action_id or "").strip().lower()
                if not action_id:
                    continue
                button = QToolButton()
                button.setText(str(action.label or action_id.title()))
                icon_name = str(action.icon_name or "").strip()
                if icon_name:
                    button.setIcon(lucide_icon(icon_name))
                tooltip = str(action.tooltip or "").strip()
                if tooltip:
                    button.setToolTip(tooltip)
                button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
                button.clicked.connect(
                    lambda _checked=False, aid=action_id: self._emit_action(aid)
                )
                self._actions_layout.addWidget(button, 0)
                self._action_buttons[action_id] = button
        self._actions_layout.addStretch(1)
        self._actions_row.setVisible(bool(self._action_buttons))
        self._apply_tone()
