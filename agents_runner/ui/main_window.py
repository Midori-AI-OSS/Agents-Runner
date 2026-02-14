from __future__ import annotations

import os
import re
import threading

from PySide6.QtCore import Qt
from PySide6.QtCore import QThread
from PySide6.QtCore import QTimer
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout
from PySide6.QtWidgets import QMainWindow
from PySide6.QtWidgets import QToolButton
from PySide6.QtWidgets import QVBoxLayout
from PySide6.QtWidgets import QWidget

from agents_runner.environments import Environment
from agents_runner.persistence import default_state_path
from agents_runner.ui.bridges import TaskRunnerBridge
from agents_runner.ui.constants import APP_TITLE
from agents_runner.ui.graphics import GlassRoot
from agents_runner.ui.lucide_icons import lucide_icon
from agents_runner.ui.radio import RadioController
from agents_runner.ui.pages import DashboardPage
from agents_runner.ui.pages import EnvironmentsPage
from agents_runner.ui.pages import NewTaskPage
from agents_runner.ui.pages import SettingsPage
from agents_runner.ui.pages import TasksPage
from agents_runner.ui.pages import TaskDetailsPage
from agents_runner.ui.task_model import Task
from agents_runner.ui.widgets import GlassCard
from agents_runner.ui.widgets.radio_control import RadioControlWidget

from agents_runner.ui.main_window_capacity import _MainWindowCapacityMixin
from agents_runner.ui.main_window_dashboard import _MainWindowDashboardMixin
from agents_runner.ui.main_window_auto_review import _MainWindowAutoReviewMixin
from agents_runner.ui.main_window_environment import _MainWindowEnvironmentMixin
from agents_runner.ui.main_window_navigation import _MainWindowNavigationMixin
from agents_runner.ui.main_window_persistence import _MainWindowPersistenceMixin
from agents_runner.ui.main_window_preflight import _MainWindowPreflightMixin
from agents_runner.ui.main_window_settings import _MainWindowSettingsMixin
from agents_runner.ui.main_window_task_events import _MainWindowTaskEventsMixin
from agents_runner.ui.main_window_task_recovery import _MainWindowTaskRecoveryMixin
from agents_runner.ui.main_window_task_review import _MainWindowTaskReviewMixin
from agents_runner.ui.main_window_tasks_agent import _MainWindowTasksAgentMixin
from agents_runner.ui.main_window_tasks_interactive import (
    _MainWindowTasksInteractiveMixin,
)
from agents_runner.ui.main_window_tasks_interactive_finalize import (
    _MainWindowTasksInteractiveFinalizeMixin,
)


class MainWindow(
    QMainWindow,
    _MainWindowCapacityMixin,
    _MainWindowNavigationMixin,
    _MainWindowSettingsMixin,
    _MainWindowEnvironmentMixin,
    _MainWindowDashboardMixin,
    _MainWindowAutoReviewMixin,
    _MainWindowTasksAgentMixin,
    _MainWindowTasksInteractiveMixin,
    _MainWindowTasksInteractiveFinalizeMixin,
    _MainWindowPreflightMixin,
    _MainWindowTaskReviewMixin,
    _MainWindowTaskRecoveryMixin,
    _MainWindowTaskEventsMixin,
    _MainWindowPersistenceMixin,
):
    host_log = Signal(str, str)
    host_pr_url = Signal(str, str)
    host_artifacts = Signal(str, object)
    interactive_finished = Signal(str, int)
    repo_branches_ready = Signal(int, object)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.setMinimumSize(1024, 640)
        self.resize(1280, 720)

        self._settings_data: dict[str, object] = {
            "use": "codex",
            "shell": "bash",
            "preflight_enabled": False,
            "preflight_script": "",
            "host_workdir": os.environ.get("CODEX_HOST_WORKDIR", os.getcwd()),
            "host_codex_dir": os.environ.get(
                "CODEX_HOST_CODEX_DIR", os.path.expanduser("~/.codex")
            ),
            "host_claude_dir": os.path.expanduser("~/.claude"),
            "host_copilot_dir": os.path.expanduser("~/.copilot"),
            "host_gemini_dir": os.path.expanduser("~/.gemini"),
            "active_environment_id": "default",
            "interactive_terminal_id": "",
            "interactive_command": "--sandbox danger-full-access",
            "interactive_command_claude": "--add-dir /home/midori-ai/workspace",
            "interactive_command_copilot": "--allow-all-tools --allow-all-paths --add-dir /home/midori-ai/workspace",
            "interactive_command_gemini": "--include-directories /home/midori-ai/workspace",
            "window_w": 1280,
            "window_h": 720,
            "max_agents_running": -1,
            "append_pixelarch_context": False,
            "headless_desktop_enabled": False,
            "auto_navigate_on_run_agent_start": False,
            "auto_navigate_on_run_interactive_start": False,
            "ui_theme": "auto",
            "popup_theme_animation_enabled": True,
            "radio_enabled": False,
            "radio_channel": "",
            "radio_quality": "medium",
            "radio_volume": 70,
            "radio_autostart": False,
            "radio_loudness_boost_enabled": False,
            "radio_loudness_boost_factor": 2.2,
            "github_workroom_prefer_browser": False,
            "github_write_confirmation_mode": "always",
            "github_poll_interval_s": 30,
            "github_polling_enabled": False,
            "github_poll_startup_delay_s": 35,
            "agentsnova_auto_review_enabled": True,
            "agentsnova_trusted_users_global": [],
            "agentsnova_review_guard_mode": "reaction",
        }
        self._environments: dict[str, Environment] = {}
        self._syncing_environment = False
        self._tasks: dict[str, Task] = {}
        self._threads: dict[str, QThread] = {}
        self._bridges: dict[str, TaskRunnerBridge] = {}
        self._interactive_prep_threads: dict[str, QThread] = {}
        self._interactive_prep_workers: dict[str, object] = {}
        self._interactive_prep_bridges: dict[str, object] = {}
        self._interactive_prep_context: dict[str, dict[str, object]] = {}
        self._run_started_s: dict[str, float] = {}
        self._dashboard_log_refresh_s: dict[str, float] = {}
        self._interactive_watch: dict[str, tuple[str, threading.Event]] = {}
        self._repo_branches_request_id: int = 0
        self._state_path = default_state_path()
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(450)
        self._save_timer.timeout.connect(self._save_state)

        # Agent watch states for cooldown tracking
        from agents_runner.core.agent.watch_state import AgentWatchState

        self._watch_states: dict[str, AgentWatchState] = {}

        self.host_log.connect(self._on_host_log, Qt.QueuedConnection)
        self.host_pr_url.connect(self._on_host_pr_url, Qt.QueuedConnection)
        self.host_artifacts.connect(self._on_host_artifacts, Qt.QueuedConnection)
        self.interactive_finished.connect(
            self._on_interactive_finished, Qt.QueuedConnection
        )
        self.repo_branches_ready.connect(
            self._on_repo_branches_ready, Qt.QueuedConnection
        )

        self._dashboard_ticker = QTimer(self)
        self._dashboard_ticker.setInterval(1000)
        self._dashboard_ticker.timeout.connect(self._tick_dashboard_elapsed)
        self._dashboard_ticker.start()

        self._recovery_log_stop: dict[str, threading.Event] = {}
        self._finalization_threads: dict[str, threading.Thread] = {}
        self._radio_channel_options: list[str] = []
        self._recovery_ticker = QTimer(self)
        # Recovery tick interval: 5 seconds (reduced from 1 second)
        # Rationale: Event-driven paths handle normal operation immediately.
        # Recovery tick is a safety net for edge cases (app restart, missed events,
        # container state sync). 5 seconds provides fast recovery while reducing
        # check frequency by 80%. See .agents/implementation/recovery-tick-timing-analysis.md
        self._recovery_ticker.setInterval(5000)
        self._recovery_ticker.timeout.connect(self._tick_recovery)
        self._recovery_ticker.start()

        self._radio_controller = RadioController(self)

        self._root = GlassRoot()
        self.setCentralWidget(self._root)

        outer = QVBoxLayout(self._root)
        outer.setContentsMargins(18, 18, 18, 18)
        outer.setSpacing(14)

        top = GlassCard()
        top_layout = QHBoxLayout(top)
        top_layout.setContentsMargins(14, 12, 14, 12)
        top_layout.setSpacing(10)

        self._btn_home = QToolButton()
        self._btn_home.setText("Home")
        self._btn_home.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self._btn_home.setIcon(lucide_icon("house"))
        self._btn_home.clicked.connect(self._show_dashboard)

        self._btn_new = QToolButton()
        self._btn_new.setText("Tasks")
        self._btn_new.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self._btn_new.setIcon(lucide_icon("folder-plus"))
        self._btn_new.clicked.connect(self._show_tasks)

        self._btn_envs = QToolButton()
        self._btn_envs.setText("Environments")
        self._btn_envs.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self._btn_envs.setIcon(lucide_icon("folder"))
        self._btn_envs.clicked.connect(self._show_environments)

        self._btn_settings = QToolButton()
        self._btn_settings.setText("Settings")
        self._btn_settings.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self._btn_settings.setIcon(lucide_icon("settings"))
        self._btn_settings.clicked.connect(self._show_settings)

        top_layout.addWidget(self._btn_home)
        top_layout.addWidget(self._btn_new)
        top_layout.addWidget(self._btn_envs)
        top_layout.addWidget(self._btn_settings)
        top_layout.addStretch(1)
        self._radio_control = RadioControlWidget(top)
        self._radio_control.setVisible(self._radio_controller.qt_available)
        top_layout.addWidget(self._radio_control, 0, Qt.AlignRight | Qt.AlignVCenter)

        self._radio_control.play_requested.connect(
            self._on_radio_control_play_requested
        )
        self._radio_control.volume_changed.connect(
            self._on_radio_control_volume_changed
        )
        self._radio_controller.state_changed.connect(
            self._on_radio_state_changed, Qt.QueuedConnection
        )

        outer.addWidget(top)

        self._dashboard = DashboardPage(
            load_past_batch_callback=self._load_past_tasks_batch
        )
        self._dashboard.task_selected.connect(self._open_task_details)
        self._dashboard.clean_old_requested.connect(self._clean_old_tasks)
        self._dashboard.task_discard_requested.connect(self._discard_task_from_ui)
        self._new_task = NewTaskPage()
        self._new_task.requested_run.connect(self._start_task_from_ui)
        self._new_task.requested_launch.connect(self._start_interactive_task_from_ui)
        self._new_task.environment_changed.connect(self._on_new_task_env_changed)
        self._new_task.back_requested.connect(self._show_dashboard)
        self._tasks_page = TasksPage(new_task_page=self._new_task)
        self._tasks_page.auto_review_requested.connect(self._on_auto_review_requested)
        self._details = TaskDetailsPage()
        self._details.set_environments(self._environments)
        self._details.back_requested.connect(self._show_dashboard)
        self._details.pr_requested.connect(self._on_task_pr_requested)
        self._details.container_action_requested.connect(self._on_task_container_action)
        self._envs_page = EnvironmentsPage()
        self._envs_page.back_requested.connect(self._show_dashboard)
        self._envs_page.updated.connect(self._reload_environments, Qt.QueuedConnection)
        self._envs_page.test_preflight_requested.connect(
            self._on_environment_test_preflight, Qt.QueuedConnection
        )
        self._settings = SettingsPage(
            radio_supported=self._radio_controller.qt_available
        )
        self._settings.back_requested.connect(self._show_dashboard)
        self._settings.saved.connect(self._apply_settings, Qt.QueuedConnection)
        self._settings.test_preflight_requested.connect(
            self._on_settings_test_preflight, Qt.QueuedConnection
        )

        self._stack = QWidget()
        self._stack_layout = QVBoxLayout(self._stack)
        self._stack_layout.setContentsMargins(0, 0, 0, 0)
        self._stack_layout.setSpacing(0)
        self._stack_layout.addWidget(self._dashboard)
        self._stack_layout.addWidget(self._tasks_page)
        self._stack_layout.addWidget(self._details)
        self._stack_layout.addWidget(self._envs_page)
        self._stack_layout.addWidget(self._settings)
        self._dashboard.show()
        self._tasks_page.hide()
        self._details.hide()
        self._envs_page.hide()
        self._settings.hide()
        outer.addWidget(self._stack, 1)

        self._load_state()
        self._sync_radio_controller_from_settings(user_initiated=False)
        self._apply_window_prefs()
        self._reload_environments()
        self._apply_settings_to_pages()
        self._refresh_radio_channel_options(disable_on_failure=True)
        self._on_radio_state_changed(self._radio_controller.state_snapshot())
        self._try_start_queued_tasks()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._settings_data["window_w"] = int(self.width())
        self._settings_data["window_h"] = int(self.height())
        if hasattr(self, "_save_timer"):
            self._schedule_save()

    def closeEvent(self, event) -> None:
        try:
            self._settings.try_autosave()
        except Exception:
            pass
        try:
            self._envs_page.try_autosave(show_validation_errors=False)
        except Exception:
            pass
        try:
            self._save_state()
        except Exception:
            pass
        if hasattr(self, "_radio_controller"):
            self._radio_controller.shutdown()
        # Clean up external viewer process
        if hasattr(self, "_details"):
            self._details.cleanup()
        super().closeEvent(event)

    def _sync_radio_controller_from_settings(
        self,
        *,
        user_initiated: bool,
        previous_enabled: bool | None = None,
    ) -> None:
        enabled = bool(self._settings_data.get("radio_enabled") or False)
        channel = RadioController.normalize_channel(
            self._settings_data.get("radio_channel")
        )
        quality = RadioController.normalize_quality(
            self._settings_data.get("radio_quality")
        )
        volume = RadioController.clamp_volume(self._settings_data.get("radio_volume"))
        autostart = bool(self._settings_data.get("radio_autostart") or False)
        loudness_boost_enabled = bool(
            self._settings_data.get("radio_loudness_boost_enabled") or False
        )
        loudness_boost_factor = RadioController.normalize_loudness_boost_factor(
            self._settings_data.get("radio_loudness_boost_factor")
        )

        self._settings_data["radio_enabled"] = enabled
        self._settings_data["radio_channel"] = channel
        self._settings_data["radio_quality"] = quality
        self._settings_data["radio_volume"] = volume
        self._settings_data["radio_autostart"] = autostart
        self._settings_data["radio_loudness_boost_enabled"] = loudness_boost_enabled
        self._settings_data["radio_loudness_boost_factor"] = loudness_boost_factor

        if not self._radio_controller.qt_available:
            self._update_window_title_from_radio_state(
                self._radio_controller.state_snapshot()
            )
            return

        self._radio_controller.set_channel(channel)
        self._radio_controller.set_quality(quality)
        self._radio_controller.set_loudness_boost(
            loudness_boost_enabled,
            loudness_boost_factor,
        )
        self._radio_controller.set_volume(volume)

        start_when_enabled = bool(
            user_initiated and enabled and previous_enabled is False
        )
        self._radio_controller.set_enabled(
            enabled,
            start_when_enabled=start_when_enabled,
        )

        if user_initiated:
            self._radio_controller.cancel_start_when_service_ready()
        elif enabled and autostart:
            self._radio_controller.request_start_when_service_ready()
        else:
            self._radio_controller.cancel_start_when_service_ready()

    def _on_radio_control_play_requested(self) -> None:
        if not self._radio_controller.qt_available:
            return

        if not bool(self._settings_data.get("radio_enabled") or False):
            self._settings_data["radio_enabled"] = True
            self._radio_controller.set_enabled(True, start_when_enabled=False)
            self._settings.set_settings(self._settings_data)

        self._radio_controller.toggle_playback()
        self._schedule_save()

    def _on_radio_control_volume_changed(self, value: int) -> None:
        clamped = RadioController.clamp_volume(value)
        self._settings_data["radio_volume"] = clamped
        self._radio_controller.set_volume(clamped)
        self._schedule_save()

    def _on_radio_state_changed(self, state: object) -> None:
        snapshot = (
            dict(state)
            if isinstance(state, dict)
            else self._radio_controller.state_snapshot()
        )
        qt_available = bool(snapshot.get("qt_available"))
        self._radio_control.setVisible(qt_available)
        if qt_available:
            self._radio_control.set_service_available(
                bool(snapshot.get("service_available"))
            )
            self._radio_control.set_playing(bool(snapshot.get("is_playing")))
            self._radio_control.set_connection_state(
                str(snapshot.get("connection_state") or "")
            )
            self._radio_control.set_radio_enabled(bool(snapshot.get("enabled")))
            try:
                volume_value = int(snapshot.get("volume") or 70)
            except Exception:
                volume_value = 70
            self._radio_control.set_volume(volume_value)
            self._radio_control.set_status_tooltip(
                str(snapshot.get("status_text") or "")
            )

        self._update_window_title_from_radio_state(snapshot)

    def _update_window_title_from_radio_state(self, state: dict[str, object]) -> None:
        if not bool(state.get("qt_available")):
            self.setWindowTitle(APP_TITLE)
            return

        channel_label = str(state.get("channel_label") or "all").strip() or "all"
        current_track = self._normalize_radio_window_track_title(
            state.get("current_track")
        )
        last_track = self._normalize_radio_window_track_title(state.get("last_track"))
        service_available = bool(state.get("service_available"))
        degraded_from_playback = bool(state.get("degraded_from_playback"))

        if degraded_from_playback and (not service_available) and last_track:
            self.setWindowTitle(f"{last_track} [{channel_label}] [Radio unavailable]")
            return

        if current_track:
            self.setWindowTitle(f"{current_track} [{channel_label}]")
            return

        self.setWindowTitle(f"{APP_TITLE} [{channel_label}]")

    def _refresh_radio_channel_options(self, *, disable_on_failure: bool) -> None:
        selected_channel = RadioController.normalize_channel(
            self._settings_data.get("radio_channel")
        )
        if not self._radio_controller.qt_available:
            self._settings.set_radio_channel_options(
                self._radio_channel_options,
                selected=selected_channel,
                enabled=False,
            )
            return

        def _handle_channels(channels: object, error_text: str) -> None:
            current_selected = RadioController.normalize_channel(
                self._settings_data.get("radio_channel")
            )

            if error_text or not isinstance(channels, list):
                if disable_on_failure:
                    self._settings.set_radio_channel_options(
                        self._radio_channel_options,
                        selected=current_selected,
                        enabled=False,
                    )
                return

            normalized: list[str] = []
            for raw in channels:
                channel = RadioController.normalize_channel(raw)
                if not channel or channel in normalized:
                    continue
                normalized.append(channel)
            normalized.sort()
            self._radio_channel_options = normalized
            self._settings.set_radio_channel_options(
                normalized,
                selected=current_selected,
                enabled=True,
            )

        self._radio_controller.fetch_channels(_handle_channels)

    @staticmethod
    def _normalize_radio_window_track_title(value: object) -> str:
        track = " ".join(str(value or "").split())
        if not track:
            return ""

        parts = [
            part.strip() for part in re.split(r"\s+[—–-]\s+", track) if part.strip()
        ]
        if not parts:
            return ""

        app_title = APP_TITLE.casefold()
        while parts and parts[0].casefold() == app_title:
            parts.pop(0)
        while len(parts) >= 2 and parts[-1].casefold() == parts[-2].casefold():
            parts.pop()
        while len(parts) >= 2 and parts[0].casefold() == parts[-1].casefold():
            parts.pop()
        while parts and parts[-1].casefold() == app_title:
            parts.pop()

        if not parts:
            return ""
        return " - ".join(parts)
