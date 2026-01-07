"""Test agent chain dialog.

Dialog for testing agent chain availability without leaking secrets.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtCore import QThread
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QDialog
from PySide6.QtWidgets import QDialogButtonBox
from PySide6.QtWidgets import QLabel
from PySide6.QtWidgets import QVBoxLayout

from agents_runner.setup.agent_status import AgentStatus
from agents_runner.setup.agent_status import detect_all_agents
from agents_runner.widgets import AgentChainStatusWidget


class AgentStatusCheckThread(QThread):
    """Background thread for checking agent status."""

    status_ready = Signal(dict)

    def __init__(self, agents: list[str], parent=None) -> None:
        super().__init__(parent)
        self._agents = agents

    def run(self) -> None:
        """Check status for all agents."""
        all_statuses = detect_all_agents()
        status_map = {status.agent: status for status in all_statuses}
        self.status_ready.emit(status_map)


class TestChainDialog(QDialog):
    """Dialog for testing agent chain availability."""

    def __init__(
        self,
        agents: list[str],
        cooldown_manager=None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._agents = agents
        self._cooldown_manager = cooldown_manager
        self._status_map: dict[str, AgentStatus] = {}

        self.setWindowTitle("Test Agent Chain")
        self.setMinimumWidth(500)
        self.setMinimumHeight(300)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Info label
        info = QLabel(
            "Testing agent availability. This checks if agents are installed "
            "and logged in, without exposing authentication details."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: rgba(237, 239, 245, 160);")
        layout.addWidget(info)

        # Status display
        self._status_widget = AgentChainStatusWidget()
        self._status_widget.test_chain_requested.connect(self._refresh)
        self._status_widget.set_chain(agents)
        layout.addWidget(self._status_widget)

        # Summary label
        self._summary = QLabel("")
        self._summary.setWordWrap(True)
        self._summary.setStyleSheet("font-weight: 600; margin-top: 8px;")
        layout.addWidget(self._summary)

        # Loading label
        self._loading = QLabel("Checking agent status...")
        self._loading.setStyleSheet("color: rgba(237, 239, 245, 120);")
        layout.addWidget(self._loading)

        layout.addStretch(1)

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # Start check
        self._refresh()

    def _refresh(self) -> None:
        """Refresh agent status check."""
        self._loading.setText("Checking agent status...")
        self._loading.setVisible(True)
        self._summary.setText("")

        # Start background check
        self._check_thread = AgentStatusCheckThread(self._agents, self)
        self._check_thread.status_ready.connect(self._on_status_ready)
        self._check_thread.start()

    def _on_status_ready(self, status_map: dict[str, AgentStatus]) -> None:
        """Handle status check completion.

        Args:
            status_map: Map of agent_name -> AgentStatus
        """
        self._status_map = status_map
        self._loading.setVisible(False)

        # Get cooldown status
        cooldowns = {}
        if self._cooldown_manager:
            for agent in self._agents:
                cooldowns[agent] = self._cooldown_manager.is_on_cooldown(agent)

        # Update display
        self._status_widget.update_statuses(status_map, cooldowns)
        summary = self._status_widget.get_availability_summary()
        self._summary.setText(summary)

        # Color the summary
        if "Available:" in summary:
            self._summary.setStyleSheet(
                "font-weight: 600; margin-top: 8px; "
                "color: rgba(95, 205, 143, 255);"
            )
        else:
            self._summary.setStyleSheet(
                "font-weight: 600; margin-top: 8px; "
                "color: rgba(249, 226, 175, 255);"
            )
