"""
Cooldown modal dialog.

Shown when user tries to run an agent that is on cooldown.
"""

from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog
from PySide6.QtWidgets import QHBoxLayout
from PySide6.QtWidgets import QLabel
from PySide6.QtWidgets import QPushButton
from PySide6.QtWidgets import QVBoxLayout
from PySide6.QtWidgets import QWidget

from agents_runner.core.agent.watch_state import AgentWatchState
from agents_runner.widgets import GlassCard


class CooldownAction:
    """User's choice in cooldown modal."""

    USE_FALLBACK = "use_fallback"
    BYPASS = "bypass"
    CANCEL = "cancel"


class CooldownModal(QDialog):
    """Modal dialog shown when agent is on cooldown."""

    def __init__(
        self,
        parent: QWidget | None,
        agent_name: str,
        watch_state: AgentWatchState,
        fallback_agent_name: str | None = None,
    ) -> None:
        """Initialize cooldown modal.

        Args:
            parent: Parent widget
            agent_name: Display name of agent on cooldown
            watch_state: Agent watch state
            fallback_agent_name: Name of fallback agent, or None if no fallback
        """
        super().__init__(parent)

        self._watch_state = watch_state
        self._result = CooldownAction.CANCEL

        self.setWindowTitle("Agent On Cooldown")
        self.setModal(True)
        self.setMinimumWidth(550)
        self.setMinimumHeight(400)

        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Warning header
        header = QLabel(f"⚠  {agent_name} is currently rate-limited")
        header.setStyleSheet(
            "font-size: 16px; font-weight: 700; color: rgba(237, 239, 245, 255);"
        )
        layout.addWidget(header)

        # Cooldown time remaining
        self._time_label = QLabel()
        self._update_time_label()
        self._time_label.setStyleSheet(
            "font-size: 14px; color: rgba(237, 239, 245, 200);"
        )
        layout.addWidget(self._time_label)

        # Reason
        if watch_state.cooldown_reason:
            reason_label = QLabel(
                f"Reason: {watch_state.cooldown_reason[:150]}"
            )
            reason_label.setStyleSheet(
                "font-size: 12px; color: rgba(237, 239, 245, 160);"
            )
            reason_label.setWordWrap(True)
            layout.addWidget(reason_label)

        # Options card
        options_card = GlassCard()
        options_layout = QVBoxLayout(options_card)
        options_layout.setContentsMargins(15, 15, 15, 15)
        options_layout.setSpacing(12)

        options_title = QLabel("Options:")
        options_title.setStyleSheet(
            "font-weight: 600; font-size: 13px; color: rgba(237, 239, 245, 255);"
        )
        options_layout.addWidget(options_title)

        # Fallback option text
        if fallback_agent_name:
            fallback_text = QLabel(
                f"• Use Fallback Agent ({fallback_agent_name})\n"
                "  Run this task with the next agent in your\n"
                "  fallback chain. This won't change your default."
            )
        else:
            fallback_text = QLabel(
                "• Use Fallback Agent (None Available)\n"
                "  No fallback agent configured."
            )
        fallback_text.setStyleSheet(
            "font-size: 12px; color: rgba(237, 239, 245, 200);"
        )
        options_layout.addWidget(fallback_text)

        # Bypass option text
        bypass_text = QLabel(
            "• Bypass Cooldown\n"
            "  Attempt to run anyway. The agent may still\n"
            "  fail if rate-limited."
        )
        bypass_text.setStyleSheet(
            "font-size: 12px; color: rgba(237, 239, 245, 200);"
        )
        options_layout.addWidget(bypass_text)

        # Cancel option text
        cancel_text = QLabel(
            "• Cancel\n" "  Don't start this task now."
        )
        cancel_text.setStyleSheet(
            "font-size: 12px; color: rgba(237, 239, 245, 200);"
        )
        options_layout.addWidget(cancel_text)

        layout.addWidget(options_card)

        layout.addStretch()

        # Buttons
        button_row = QHBoxLayout()
        button_row.setSpacing(10)
        button_row.addStretch()

        self._fallback_btn = QPushButton("Use Fallback")
        self._fallback_btn.setEnabled(bool(fallback_agent_name))
        self._fallback_btn.clicked.connect(self._on_use_fallback)
        self._fallback_btn.setMinimumWidth(120)
        button_row.addWidget(self._fallback_btn)

        bypass_btn = QPushButton("Bypass")
        bypass_btn.clicked.connect(self._on_bypass)
        bypass_btn.setMinimumWidth(100)
        button_row.addWidget(bypass_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self._on_cancel)
        cancel_btn.setMinimumWidth(100)
        button_row.addWidget(cancel_btn)

        layout.addLayout(button_row)

        # Update time every second
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_time_label)
        self._timer.start(1000)  # 1 second

    def _update_time_label(self) -> None:
        """Update cooldown time remaining label."""
        remaining = self._watch_state.cooldown_seconds_remaining()
        if remaining <= 0:
            self._time_label.setText("Cooldown Time Remaining: Expired")
        else:
            minutes = int(remaining // 60)
            seconds = int(remaining % 60)
            if minutes > 0:
                self._time_label.setText(
                    f"Cooldown Time Remaining: {minutes}m {seconds}s"
                )
            else:
                self._time_label.setText(
                    f"Cooldown Time Remaining: {seconds} seconds"
                )

    def _on_use_fallback(self) -> None:
        """Handle Use Fallback button."""
        self._result = CooldownAction.USE_FALLBACK
        self.accept()

    def _on_bypass(self) -> None:
        """Handle Bypass button."""
        self._result = CooldownAction.BYPASS
        self.accept()

    def _on_cancel(self) -> None:
        """Handle Cancel button."""
        self._result = CooldownAction.CANCEL
        self.reject()

    def get_result(self) -> str:
        """Get user's choice."""
        return self._result
