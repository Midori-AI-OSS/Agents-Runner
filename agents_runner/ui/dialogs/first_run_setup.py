"""First-run setup dialog for agent authentication.

This module provides the first-run setup experience, showing users
which agents are installed and allowing them to set up authentication
in a sequential flow.
"""

import asyncio

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QCheckBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QProgressBar,
    QWidget,
)

from agents_runner.setup.agent_status import detect_all_agents, AgentStatus, StatusType
from agents_runner.setup.orchestrator import (
    SetupOrchestrator,
    mark_setup_complete,
    mark_setup_skipped,
)
from agents_runner.ui.dialogs.docker_validator import DockerValidator


class FirstRunSetupDialog(QDialog):
    """First-run setup dialog shown on app launch if setup incomplete."""

    def __init__(self, parent: QWidget | None = None):
        """Initialize first-run setup dialog.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self.setWindowTitle("Agents Runner - First-Time Setup")
        self.setModal(True)
        self.setMinimumWidth(700)
        self.setMinimumHeight(500)

        self._agent_statuses: list[AgentStatus] = []
        self._checkboxes: dict[str, QCheckBox] = {}
        self._orchestrator: SetupOrchestrator | None = None
        self._docker_validator: DockerValidator | None = None

        self._setup_ui()
        self._detect_agents()

    def _setup_ui(self) -> None:
        """Set up the dialog UI."""
        layout = QVBoxLayout()
        self.setLayout(layout)

        # Welcome message
        welcome_label = QLabel("Welcome to Agents Runner!")
        welcome_label.setStyleSheet("font-size: 18px; font-weight: 700;")
        layout.addWidget(welcome_label)

        intro_label = QLabel(
            "We detected the following AI agent CLIs on your system.\n"
            "Select which agents you'd like to set up now."
        )
        intro_label.setWordWrap(True)
        layout.addWidget(intro_label)

        # Agent status table
        self._status_table = QTableWidget()
        self._status_table.setColumnCount(4)
        self._status_table.setHorizontalHeaderLabels(
            ["Agent", "Installed", "Login Status", "Setup"]
        )
        self._status_table.horizontalHeader().setStretchLastSection(False)
        self._status_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self._status_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self._status_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )
        self._status_table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.ResizeToContents
        )
        self._status_table.verticalHeader().setVisible(False)
        self._status_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self._status_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self._status_table)

        # Instructions
        instructions_label = QLabel(
            "Setup will open one terminal at a time. Complete each agent's setup "
            "before moving to the next."
        )
        instructions_label.setWordWrap(True)
        instructions_label.setStyleSheet("color: #666; font-size: 11px;")
        instructions_label.setToolTip(
            "You can configure individual agents later in Settings → Agent CLI section."
        )
        layout.addWidget(instructions_label)

        # Docker check section
        docker_section = QWidget()
        docker_layout = QVBoxLayout(docker_section)
        docker_layout.setContentsMargins(0, 10, 0, 0)
        docker_layout.setSpacing(6)

        docker_title = QLabel("Docker Validation (Optional)")
        docker_title.setStyleSheet("font-weight: 600;")
        docker_layout.addWidget(docker_title)

        docker_desc = QLabel(
            "Verify Docker is working by pulling PixelArch and running a test container."
        )
        docker_desc.setWordWrap(True)
        docker_desc.setStyleSheet("color: #666; font-size: 11px;")
        docker_layout.addWidget(docker_desc)

        self._docker_status_label = QLabel("")
        self._docker_status_label.setWordWrap(True)
        self._docker_status_label.setStyleSheet("font-size: 11px;")
        docker_layout.addWidget(self._docker_status_label)

        self._docker_check_button = QPushButton("Check Docker")
        self._docker_check_button.clicked.connect(self._on_check_docker)
        docker_layout.addWidget(self._docker_check_button)

        layout.addWidget(docker_section)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self._skip_button = QPushButton("Skip Setup")
        self._skip_button.clicked.connect(self._on_skip)
        button_layout.addWidget(self._skip_button)

        self._begin_button = QPushButton("Begin Setup")
        self._begin_button.clicked.connect(self._on_begin_setup)
        self._begin_button.setDefault(True)
        button_layout.addWidget(self._begin_button)

        layout.addLayout(button_layout)

    def _detect_agents(self) -> None:
        """Detect all agents and populate the table."""
        self._agent_statuses = detect_all_agents()

        # Clear existing rows
        self._status_table.setRowCount(0)

        for status in self._agent_statuses:
            row = self._status_table.rowCount()
            self._status_table.insertRow(row)

            # Agent name
            name_item = QTableWidgetItem(status.agent.capitalize())
            self._status_table.setItem(row, 0, name_item)

            # Installed status
            installed_text = "✓ Installed" if status.installed else "✗ Not installed"
            installed_item = QTableWidgetItem(installed_text)
            if status.installed:
                installed_item.setForeground(Qt.GlobalColor.darkGreen)
            else:
                installed_item.setForeground(Qt.GlobalColor.red)
            self._status_table.setItem(row, 1, installed_item)

            # Login status
            login_item = QTableWidgetItem(status.status_text)
            if status.status_type == StatusType.LOGGED_IN:
                login_item.setForeground(Qt.GlobalColor.darkGreen)
            elif status.status_type == StatusType.NOT_LOGGED_IN:
                login_item.setForeground(Qt.GlobalColor.darkYellow)
            elif status.status_type == StatusType.UNKNOWN:
                login_item.setForeground(Qt.GlobalColor.gray)
            else:
                login_item.setForeground(Qt.GlobalColor.red)
            self._status_table.setItem(row, 2, login_item)

            # Setup checkbox
            checkbox = QCheckBox()
            # Pre-check if installed and not logged in
            if status.installed and not status.logged_in:
                checkbox.setChecked(True)
            # Disable if not installed or already logged in
            if not status.installed or status.logged_in:
                checkbox.setEnabled(False)
            self._checkboxes[status.agent] = checkbox

            checkbox_widget = QWidget()
            checkbox_layout = QHBoxLayout(checkbox_widget)
            checkbox_layout.addWidget(checkbox)
            checkbox_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            checkbox_layout.setContentsMargins(0, 0, 0, 0)
            self._status_table.setCellWidget(row, 3, checkbox_widget)

    def _on_check_docker(self) -> None:
        """Handle Docker check button click."""
        if self._docker_validator is None:
            self._docker_validator = DockerValidator(self)

        # Update UI callback
        def update_status(message: str, color: str) -> None:
            self._docker_status_label.setText(message)
            self._docker_status_label.setStyleSheet(f"color: {color}; font-size: 11px;")

        # Completion callback
        def on_complete(success: bool) -> None:
            self._docker_check_button.setEnabled(True)
            if not success:
                self._docker_check_button.setText("Try Again")

        self._docker_check_button.setEnabled(False)
        self._docker_check_button.setText("Check Docker")
        self._docker_validator.start_validation(update_status, on_complete)

    def _on_skip(self) -> None:
        """Handle skip button click."""
        mark_setup_skipped()
        self.accept()

    def _on_begin_setup(self) -> None:
        """Handle begin setup button click."""
        # Get selected agents
        selected_agents = [
            agent
            for agent, checkbox in self._checkboxes.items()
            if checkbox.isChecked()
        ]

        if not selected_agents:
            # Nothing to set up
            mark_setup_skipped()
            self.accept()
            return

        # Show progress dialog
        progress_dialog = SetupProgressDialog(selected_agents, self)
        result = progress_dialog.exec()

        if result == QDialog.DialogCode.Accepted:
            # Setup complete
            agents_setup = progress_dialog.get_results()
            agents_enabled = {
                agent: checkbox.isChecked()
                for agent, checkbox in self._checkboxes.items()
            }
            mark_setup_complete(agents_setup, agents_enabled, cancelled=False)
            self.accept()
        else:
            # Setup cancelled
            agents_setup = progress_dialog.get_results()
            agents_enabled = {
                agent: checkbox.isChecked()
                for agent, checkbox in self._checkboxes.items()
            }
            mark_setup_complete(agents_setup, agents_enabled, cancelled=True)
            self.reject()


class SetupProgressDialog(QDialog):
    """Progress dialog shown during sequential agent setup."""

    def __init__(self, agents: list[str], parent: QWidget | None = None):
        """Initialize progress dialog.

        Args:
            agents: List of agent names to set up
            parent: Parent widget
        """
        super().__init__(parent)
        self.setWindowTitle("Agent Setup Progress")
        self.setModal(True)
        self.setMinimumWidth(500)
        self.setMinimumHeight(300)

        self._agents = agents
        self._results: dict[str, bool] = {}
        self._orchestrator = SetupOrchestrator(delay_seconds=2.0)

        self._setup_ui()
        # Start setup after dialog is shown
        QTimer.singleShot(100, self._start_setup)

    def _setup_ui(self) -> None:
        """Set up the progress dialog UI."""
        layout = QVBoxLayout()
        self.setLayout(layout)

        # Title
        self._title_label = QLabel("Setting up agents...")
        self._title_label.setStyleSheet("font-size: 14px; font-weight: 700;")
        layout.addWidget(self._title_label)

        # Current agent
        self._current_label = QLabel("Current: None")
        layout.addWidget(self._current_label)

        # Status message
        self._status_label = QLabel("Starting setup...")
        layout.addWidget(self._status_label)

        # Progress bar
        self._progress_bar = QProgressBar()
        self._progress_bar.setMinimum(0)
        self._progress_bar.setMaximum(len(self._agents))
        self._progress_bar.setValue(0)
        layout.addWidget(self._progress_bar)

        # Completed/remaining
        self._completed_label = QLabel("Completed: None")
        self._completed_label.setWordWrap(True)
        layout.addWidget(self._completed_label)

        self._remaining_label = QLabel(f"Remaining: {', '.join(self._agents)}")
        self._remaining_label.setWordWrap(True)
        layout.addWidget(self._remaining_label)

        layout.addStretch()

        # Cancel button
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        self._cancel_button = QPushButton("Cancel Setup")
        self._cancel_button.clicked.connect(self._on_cancel)
        button_layout.addWidget(self._cancel_button)
        layout.addLayout(button_layout)

    def _start_setup(self) -> None:
        """Start the sequential setup process."""
        # Run setup in background
        asyncio.create_task(self._run_setup())

    async def _run_setup(self) -> None:
        """Run the setup orchestration."""
        results = await self._orchestrator.run_sequential_setup(
            self._agents, progress_callback=self._on_progress
        )
        self._results = results
        # All done
        self._title_label.setText("Setup Complete!")
        self._status_label.setText("All agents have been set up.")
        self._cancel_button.setText("Close")
        # Auto-close after 1 second
        QTimer.singleShot(1000, self.accept)

    def _on_progress(
        self, agent: str, current: int, total: int, status_message: str
    ) -> None:
        """Handle progress update from orchestrator.

        Args:
            agent: Current agent being set up
            current: Current agent index (1-based)
            total: Total number of agents
            status_message: Status message to display
        """
        self._title_label.setText(f"Setting up agent {current} of {total}")
        self._current_label.setText(f"Current: {agent.capitalize()}")
        self._status_label.setText(status_message)
        self._progress_bar.setValue(
            current - 1 if "Starting in" in status_message else current
        )

        # Update completed/remaining lists
        completed = [a for a in self._agents[: current - 1]]
        remaining = [a for a in self._agents[current:]]

        completed_text = (
            ", ".join([a.capitalize() for a in completed]) if completed else "None"
        )
        remaining_text = (
            ", ".join([a.capitalize() for a in remaining]) if remaining else "None"
        )

        self._completed_label.setText(f"Completed: {completed_text}")
        self._remaining_label.setText(f"Remaining: {remaining_text}")

    def _on_cancel(self) -> None:
        """Handle cancel button click."""
        self._orchestrator.cancel()
        self.reject()

    def get_results(self) -> dict[str, bool]:
        """Get the setup results.

        Returns:
            Dict mapping agent name to success status
        """
        return self._results
