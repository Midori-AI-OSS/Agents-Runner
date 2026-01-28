"""Agent chain status display widget.

Shows agent availability status in a clear, visual way for fallback chains.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout
from PySide6.QtWidgets import QLabel
from PySide6.QtWidgets import QToolButton
from PySide6.QtWidgets import QVBoxLayout
from PySide6.QtWidgets import QWidget

from agents_runner.setup.agent_status import AgentStatus


class AgentStatusIndicator(QWidget):
    """Single agent status indicator with icons."""

    def __init__(
        self,
        agent_name: str,
        position: int,
        total: int,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._agent_name = agent_name
        self._position = position
        self._total = total
        self._status: AgentStatus | None = None
        self._on_cooldown = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Position indicator
        position_label = QLabel(f"{position}.")
        position_label.setStyleSheet(
            "color: rgba(237, 239, 245, 120); font-weight: 600;"
        )
        layout.addWidget(position_label)

        # Agent name
        self._name_label = QLabel(agent_name.title())
        self._name_label.setStyleSheet("font-weight: 500;")
        layout.addWidget(self._name_label)

        # Status indicators container
        self._status_container = QWidget()
        self._status_layout = QHBoxLayout(self._status_container)
        self._status_layout.setContentsMargins(0, 0, 0, 0)
        self._status_layout.setSpacing(4)
        layout.addWidget(self._status_container)

        layout.addStretch(1)

        self._update_display()

    def set_status(self, status: AgentStatus | None, on_cooldown: bool = False) -> None:
        """Update agent status.

        Args:
            status: Agent installation/login status
            on_cooldown: Whether agent is currently on cooldown
        """
        self._status = status
        self._on_cooldown = on_cooldown
        self._update_display()

    def _update_display(self) -> None:
        """Update status indicator display."""
        # Clear existing indicators
        while self._status_layout.count():
            item = self._status_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self._status:
            # Unknown status
            self._add_indicator("?", "Unknown", "rgba(160, 160, 160, 255)")
            return

        # Installed indicator
        if self._status.installed:
            self._add_indicator(
                "✓", "Installed", "rgba(95, 205, 143, 255)"
            )
        else:
            self._add_indicator(
                "✕", "Not installed", "rgba(243, 139, 168, 255)"
            )

        # Logged in indicator
        if self._status.installed:
            if self._status.logged_in:
                self._add_indicator(
                    "✓", "Logged in", "rgba(95, 205, 143, 255)"
                )
            else:
                self._add_indicator(
                    "⚠", "Not logged in", "rgba(249, 226, 175, 255)"
                )

        # Cooldown indicator
        if self._on_cooldown:
            self._add_indicator(
                "❄", "On cooldown", "rgba(137, 180, 250, 255)"
            )
        elif self._status.installed and self._status.logged_in:
            self._add_indicator(
                "✓", "Available", "rgba(95, 205, 143, 255)"
            )

    def _add_indicator(self, icon: str, tooltip: str, color: str) -> None:
        """Add a status indicator.

        Args:
            icon: Icon character to display
            tooltip: Tooltip text
            color: Text color (rgba format)
        """
        label = QLabel(icon)
        label.setToolTip(tooltip)
        label.setStyleSheet(f"color: {color}; font-weight: 600;")
        self._status_layout.addWidget(label)

    def get_agent_name(self) -> str:
        """Get agent name."""
        return self._agent_name

    def is_available(self) -> bool:
        """Check if agent is available for use."""
        if not self._status:
            return False
        if not self._status.installed or not self._status.logged_in:
            return False
        if self._on_cooldown:
            return False
        return True


class AgentChainStatusWidget(QWidget):
    """Display agent chain with status indicators."""

    test_chain_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._agent_indicators: list[AgentStatusIndicator] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Header
        header_layout = QHBoxLayout()
        header_layout.setSpacing(10)

        header_label = QLabel("Agent Chain (Primary → Fallbacks):")
        header_label.setStyleSheet(
            "font-weight: 600; color: rgba(237, 239, 245, 200);"
        )
        header_layout.addWidget(header_label)
        header_layout.addStretch(1)

        # Test Chain button
        self._test_btn = QToolButton()
        self._test_btn.setText("Test Chain")
        self._test_btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self._test_btn.clicked.connect(self.test_chain_requested.emit)
        header_layout.addWidget(self._test_btn)

        layout.addLayout(header_layout)

        # Chain display area
        self._chain_layout = QVBoxLayout()
        self._chain_layout.setSpacing(4)
        layout.addLayout(self._chain_layout)

    def set_chain(self, agents: list[str]) -> None:
        """Set agent chain to display.

        Args:
            agents: List of agent names in priority order
        """
        # Clear existing indicators
        while self._chain_layout.count():
            item = self._chain_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._agent_indicators.clear()

        if not agents:
            no_agents = QLabel("No agents configured")
            no_agents.setStyleSheet("color: rgba(237, 239, 245, 120);")
            self._chain_layout.addWidget(no_agents)
            self._test_btn.setEnabled(False)
            return

        # Create indicators for each agent
        for i, agent in enumerate(agents):
            indicator = AgentStatusIndicator(agent, i + 1, len(agents))
            self._agent_indicators.append(indicator)
            self._chain_layout.addWidget(indicator)

        self._test_btn.setEnabled(True)

    def update_statuses(
        self,
        statuses: dict[str, AgentStatus],
        cooldowns: dict[str, bool],
    ) -> None:
        """Update status indicators for all agents.

        Args:
            statuses: Map of agent_name -> AgentStatus
            cooldowns: Map of agent_name -> is_on_cooldown
        """
        for indicator in self._agent_indicators:
            agent_name = indicator.get_agent_name()
            status = statuses.get(agent_name)
            on_cooldown = cooldowns.get(agent_name, False)
            indicator.set_status(status, on_cooldown)

    def get_availability_summary(self) -> str:
        """Get summary of chain availability.

        Returns:
            Human-readable summary string
        """
        if not self._agent_indicators:
            return "No agents configured"

        available = []
        unavailable = []

        for indicator in self._agent_indicators:
            name = indicator.get_agent_name().title()
            if indicator.is_available():
                available.append(name)
            else:
                unavailable.append(name)

        if available:
            return f"Available: {' → '.join(available)}"
        else:
            return "No agents currently available"
