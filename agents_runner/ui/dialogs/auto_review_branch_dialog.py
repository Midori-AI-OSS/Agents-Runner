from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QComboBox
from PySide6.QtWidgets import QDialogButtonBox
from PySide6.QtWidgets import QLabel
from PySide6.QtWidgets import QVBoxLayout
from PySide6.QtWidgets import QWidget

from agents_runner.ui.dialogs.themed_dialog import ThemedDialog
from agents_runner.ui.widgets import GlassCard


class AutoReviewBranchDialog(ThemedDialog):
    def __init__(
        self,
        *,
        environment_name: str,
        previous_branch: str,
        branches: list[str],
        timeout_seconds: int = 15,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._seconds_left = max(1, int(timeout_seconds))
        self._timeout_timer = QTimer(self)
        self._timeout_timer.timeout.connect(self._on_timeout_tick)

        self.setModal(True)
        self.setWindowTitle("Auto-Review Base Branch")
        self.setMinimumWidth(620)

        layout = self.content_layout()
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        content_card = GlassCard()
        content_layout = QVBoxLayout(content_card)
        content_layout.setContentsMargins(14, 12, 14, 12)
        content_layout.setSpacing(8)
        layout.addWidget(content_card)

        message = QLabel(
            "Saved base branch "
            f"'{previous_branch or '(none)'}' is no longer available for "
            f"{environment_name or '(unknown)'}."
        )
        message.setStyleSheet("font-size: 15px; font-weight: 700;")
        message.setWordWrap(True)
        content_layout.addWidget(message)

        branch_label = QLabel("Base branch")
        branch_label.setStyleSheet("font-weight: 650;")
        self._branch_combo = QComboBox()
        self.set_branches(branches=branches, selected=previous_branch)
        content_layout.addWidget(branch_label)
        content_layout.addWidget(self._branch_combo)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self._ok_button = buttons.button(QDialogButtonBox.Ok)
        content_layout.addWidget(buttons)

        self._update_countdown_text()
        self._timeout_timer.start(1000)

    def done(self, result: int) -> None:
        if self._timeout_timer.isActive():
            self._timeout_timer.stop()
        super().done(result)

    def selected_branch(self) -> str:
        return str(self._branch_combo.currentData() or "").strip()

    def set_branches(self, *, branches: list[str], selected: str | None = None) -> None:
        wanted = str(selected or "").strip()
        self._branch_combo.blockSignals(True)
        try:
            self._branch_combo.clear()
            self._branch_combo.addItem("Auto", "")
            for name in branches or []:
                branch = str(name or "").strip()
                if not branch:
                    continue
                self._branch_combo.addItem(branch, branch)
            if wanted:
                idx = self._branch_combo.findData(wanted)
                if idx >= 0:
                    self._branch_combo.setCurrentIndex(idx)
                    return
            self._branch_combo.setCurrentIndex(0)
        finally:
            self._branch_combo.blockSignals(False)

    def _update_countdown_text(self) -> None:
        self._ok_button.setText(f"OK ({self._seconds_left}s)")

    def _on_timeout_tick(self) -> None:
        self._seconds_left -= 1
        if self._seconds_left <= 0:
            self.accept()
            return
        self._update_countdown_text()
