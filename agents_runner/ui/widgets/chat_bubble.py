from __future__ import annotations

import html
import importlib

from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QEvent
from PySide6.QtCore import QPointF
from PySide6.QtCore import Qt
from PySide6.QtCore import Signal
from PySide6.QtGui import QEnterEvent
from PySide6.QtGui import QPaintEvent
from PySide6.QtGui import QPainter
from PySide6.QtGui import QPainterPath
from PySide6.QtGui import QPolygonF
from PySide6.QtWidgets import QHBoxLayout
from PySide6.QtWidgets import QLabel
from PySide6.QtWidgets import QLayout
from PySide6.QtWidgets import QSizePolicy
from PySide6.QtWidgets import QToolButton
from PySide6.QtWidgets import QVBoxLayout
from PySide6.QtWidgets import QWidget

from agents_runner.ui.lucide_icons import lucide_icon
from agents_runner.ui.utils import ChatBubbleTone
from agents_runner.ui.utils import resolve_chat_bubble_tone
from agents_runner.ui.utils import rgba


def _load_markdown_module() -> Any | None:
    try:
        return importlib.import_module("markdown")
    except Exception:
        return None


_MARKDOWN_MODULE: Any | None = _load_markdown_module()


def _fallback_plain_html(source: str) -> str:
    escaped = html.escape(str(source or ""))
    escaped = escaped.replace("\r\n", "\n").replace("\r", "\n")
    escaped = escaped.replace("\n", "<br/>")
    return f"<p>{escaped}</p>"


def _render_markdown_html(source: str) -> str:
    module = _MARKDOWN_MODULE
    if module is None:
        return _fallback_plain_html(source)

    try:
        rendered = str(
            module.markdown(
                str(source or ""),
                extensions=[
                    "fenced_code",
                    "tables",
                    "sane_lists",
                    "nl2br",
                    "codehilite",
                ],
                extension_configs={
                    "codehilite": {
                        "guess_lang": False,
                        "noclasses": True,
                        "pygments_style": "monokai",
                    }
                },
                output_format="html5",
            )
            or ""
        ).strip()
    except Exception:
        return _fallback_plain_html(source)

    if not rendered:
        return "<p></p>"

    styled = rendered.replace(
        "<pre>",
        (
            "<pre style='margin: 8px 0; padding: 8px; border: 1px solid "
            "rgba(141, 149, 164, 0.45); background-color: rgba(11, 13, 18, 0.85); "
            "white-space: pre-wrap; word-wrap: break-word;'>"
        ),
    )
    styled = styled.replace(
        "<code>",
        (
            "<code style='font-family: JetBrains Mono, Fira Code, "
            "DejaVu Sans Mono, monospace;'>"
        ),
    )
    return styled


def _clear_layout(layout: QLayout) -> None:
    while layout.count() > 0:
        item = layout.takeAt(0)
        if item is None:
            continue
        widget = item.widget()
        if widget is not None:
            widget.setParent(None)


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
    delete_requested = Signal()

    _MAX_BUBBLE_WIDTH = 720

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._tone = resolve_chat_bubble_tone(
            role="other", env_stain="slate", username="unknown"
        )
        self._flipped = False
        self._timestamp_text = ""
        self._body_source = ""
        self._action_buttons: dict[str, QToolButton] = {}

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)
        self._root = root

        self._hover_timestamp = QLabel("")
        self._hover_timestamp.setVisible(False)
        self._hover_timestamp.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self._surface = _BubbleSurface()
        self._surface.setMaximumWidth(self._MAX_BUBBLE_WIDTH)
        self._surface.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        content = QVBoxLayout(self._surface)
        content.setContentsMargins(12, 9, 12, 14)
        content.setSpacing(6)
        self._content_layout = content

        self._header_layout = QHBoxLayout()
        self._header_layout.setContentsMargins(0, 0, 0, 0)
        self._header_layout.setSpacing(8)

        self._author = QLabel("unknown")
        self._author.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self._actions_host = QWidget()
        self._actions_layout = QHBoxLayout(self._actions_host)
        self._actions_layout.setContentsMargins(0, 0, 0, 0)
        self._actions_layout.setSpacing(4)

        self._content_layout.addLayout(self._header_layout)

        self._body = QLabel("")
        self._body.setWordWrap(True)
        self._body.setTextFormat(Qt.RichText)
        self._body.setOpenExternalLinks(True)
        self._body.setTextInteractionFlags(
            Qt.TextSelectableByMouse | Qt.LinksAccessibleByMouse
        )
        self._content_layout.addWidget(self._body)

        self._apply_alignment()
        self._apply_tone()

    def _set_hover_timestamp_visible(self, visible: bool) -> None:
        self._hover_timestamp.setVisible(bool(visible and self._timestamp_text.strip()))

    def _apply_alignment(self) -> None:
        _clear_layout(self._root)

        if self._flipped:
            self._root.addWidget(self._hover_timestamp, 0, Qt.AlignLeft | Qt.AlignTop)
            self._root.addStretch(1)
            self._root.addWidget(self._surface, 0)
            self._surface.set_tail_side("right")
        else:
            self._root.addWidget(self._surface, 0)
            self._root.addStretch(1)
            self._root.addWidget(self._hover_timestamp, 0, Qt.AlignRight | Qt.AlignTop)
            self._surface.set_tail_side("left")

        _clear_layout(self._header_layout)
        if self._flipped:
            self._header_layout.addWidget(self._author, 0)
            self._header_layout.addStretch(1)
            self._header_layout.addWidget(self._actions_host, 0, Qt.AlignRight)
        else:
            self._header_layout.addWidget(self._actions_host, 0, Qt.AlignLeft)
            self._header_layout.addWidget(self._author, 0)
            self._header_layout.addStretch(1)

    def _render_body(self) -> None:
        rendered = _render_markdown_html(self._body_source)
        self._body.setText(f"<div style='margin: 0; padding: 0;'>{rendered}</div>")

    def _apply_tone(self) -> None:
        self._surface.set_tone(self._tone)
        self._author.setStyleSheet(
            f"font-size: 13px; font-weight: 700; color: {rgba(self._tone.text_primary)};"
        )
        self._hover_timestamp.setStyleSheet(
            f"font-size: 12px; color: {rgba(self._tone.text_secondary)};"
        )
        self._body.setStyleSheet(
            "\n".join(
                [
                    "QLabel {",
                    "  font-size: 13px;",
                    "  font-weight: 500;",
                    f"  color: {rgba(self._tone.text_primary)};",
                    "}",
                    "QLabel a {",
                    f"  color: {rgba(self._tone.text_primary)};",
                    "  text-decoration: underline;",
                    "}",
                ]
            )
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
                        "  padding: 4px;",
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
            if item is None:
                continue
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
        elif action == "delete":
            self.delete_requested.emit()

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
        self._timestamp_text = str(data.timestamp or "")
        self._hover_timestamp.setText(self._timestamp_text)
        self._set_hover_timestamp_visible(False)

        self._body_source = str(data.body or "")
        self._render_body()

        self._clear_action_buttons()
        if data.actions:
            for action in data.actions:
                action_id = str(action.action_id or "").strip().lower()
                if not action_id:
                    continue
                button = QToolButton()
                button.setToolButtonStyle(Qt.ToolButtonIconOnly)
                button.setFixedSize(24, 24)
                icon_name = str(action.icon_name or "").strip()
                if icon_name:
                    button.setIcon(lucide_icon(icon_name))
                tooltip = str(action.tooltip or "").strip()
                if not tooltip:
                    tooltip = str(action.label or action_id.title())
                button.setToolTip(tooltip)
                button.clicked.connect(
                    lambda _checked=False, aid=action_id: self._emit_action(aid)
                )
                self._actions_layout.addWidget(button, 0)
                self._action_buttons[action_id] = button

        self._actions_host.setVisible(bool(self._action_buttons))
        self._apply_tone()

    def enterEvent(self, event: QEnterEvent) -> None:
        super().enterEvent(event)
        self._set_hover_timestamp_visible(True)

    def leaveEvent(self, event: QEvent) -> None:
        super().leaveEvent(event)
        self._set_hover_timestamp_visible(False)
