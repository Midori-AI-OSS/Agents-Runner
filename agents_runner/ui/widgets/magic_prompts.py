from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QPushButton
from PySide6.QtWidgets import QVBoxLayout
from PySide6.QtWidgets import QWidget

from agents_runner.magic_prompts import load_magic_prompts


class MagicPromptsWidget(QWidget):
    prompt_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        prompts = load_magic_prompts()
        for entry in prompts:
            title = str(entry.get("title") or "").strip()
            prompt_text = str(entry.get("prompt") or "").strip()
            if not title or not prompt_text:
                continue
            button = QPushButton(title)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setStyleSheet(
                "QPushButton {"
                "  text-align: left;"
                "  padding: 6px 10px;"
                "  border: 1px solid rgba(237, 239, 245, 35);"
                "  border-radius: 0px;"
                "  background-color: rgba(18, 20, 28, 160);"
                "  color: rgba(237, 239, 245, 210);"
                "  font-size: 13px;"
                "}"
                "QPushButton:hover {"
                "  background-color: rgba(237, 239, 245, 15);"
                "  border-color: rgba(237, 239, 245, 70);"
                "}"
                "QPushButton:pressed {"
                "  background-color: rgba(237, 239, 245, 25);"
                "}"
            )
            button.clicked.connect(lambda _checked=False, text=prompt_text: self.prompt_selected.emit(text))
            layout.addWidget(button)

        layout.addStretch(1)
