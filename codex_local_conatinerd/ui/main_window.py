from __future__ import annotations

import os
import threading

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtCore import QThread
from PySide6.QtCore import QTimer
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout
from PySide6.QtWidgets import QMainWindow
from PySide6.QtWidgets import QStyle
from PySide6.QtWidgets import QToolButton
from PySide6.QtWidgets import QVBoxLayout
from PySide6.QtWidgets import QWidget

from codex_local_conatinerd.environments import Environment
from codex_local_conatinerd.persistence import default_state_path
from codex_local_conatinerd.ui.bridges import HostCleanupBridge
from codex_local_conatinerd.ui.bridges import TaskRunnerBridge
from codex_local_conatinerd.ui.constants import APP_TITLE
from codex_local_conatinerd.ui.graphics import GlassRoot
from codex_local_conatinerd.ui.pages import DashboardPage
from codex_local_conatinerd.ui.pages import EnvironmentsPage
from codex_local_conatinerd.ui.pages import NewTaskPage
from codex_local_conatinerd.ui.pages import SettingsPage
from codex_local_conatinerd.ui.pages import TaskDetailsPage
from codex_local_conatinerd.ui.task_model import Task
from codex_local_conatinerd.widgets import GlassCard

from codex_local_conatinerd.ui.main_window_capacity import _MainWindowCapacityMixin
from codex_local_conatinerd.ui.main_window_cleanup import _MainWindowCleanupMixin
from codex_local_conatinerd.ui.main_window_dashboard import _MainWindowDashboardMixin
from codex_local_conatinerd.ui.main_window_environment import _MainWindowEnvironmentMixin
from codex_local_conatinerd.ui.main_window_navigation import _MainWindowNavigationMixin
from codex_local_conatinerd.ui.main_window_persistence import _MainWindowPersistenceMixin
from codex_local_conatinerd.ui.main_window_preflight import _MainWindowPreflightMixin
from codex_local_conatinerd.ui.main_window_settings import _MainWindowSettingsMixin
from codex_local_conatinerd.ui.main_window_task_events import _MainWindowTaskEventsMixin
from codex_local_conatinerd.ui.main_window_task_review import _MainWindowTaskReviewMixin
from codex_local_conatinerd.ui.main_window_tasks_agent import _MainWindowTasksAgentMixin
from codex_local_conatinerd.ui.main_window_tasks_interactive import _MainWindowTasksInteractiveMixin
from codex_local_conatinerd.ui.main_window_tasks_interactive_finalize import (
    _MainWindowTasksInteractiveFinalizeMixin,
)


class MainWindow(
    QMainWindow,
    _MainWindowCleanupMixin,
    _MainWindowCapacityMixin,
    _MainWindowNavigationMixin,
    _MainWindowSettingsMixin,
    _MainWindowEnvironmentMixin,
    _MainWindowDashboardMixin,
    _MainWindowTasksAgentMixin,
    _MainWindowTasksInteractiveMixin,
    _MainWindowTasksInteractiveFinalizeMixin,
    _MainWindowPreflightMixin,
    _MainWindowTaskReviewMixin,
    _MainWindowTaskEventsMixin,
    _MainWindowPersistenceMixin,
):
    host_log = Signal(str, str)
    host_pr_url = Signal(str, str)
    interactive_finished = Signal(str, int)

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
            "host_codex_dir": os.environ.get("CODEX_HOST_CODEX_DIR", os.path.expanduser("~/.codex")),
            "host_claude_dir": "",
            "host_copilot_dir": "",
            "active_environment_id": "default",
            "interactive_terminal_id": "",
            "interactive_command": "--sandbox danger-full-access",
            "interactive_command_claude": "--add-dir /home/midori-ai/workspace",
            "interactive_command_copilot": "--add-dir /home/midori-ai/workspace",
            "window_w": 1280,
            "window_h": 720,
            "max_agents_running": -1,
            "append_pixelarch_context": False,
        }
        self._environments: dict[str, Environment] = {}
        self._syncing_environment = False
        self._tasks: dict[str, Task] = {}
        self._threads: dict[str, QThread] = {}
        self._bridges: dict[str, TaskRunnerBridge] = {}
        self._run_started_s: dict[str, float] = {}
        self._dashboard_log_refresh_s: dict[str, float] = {}
        self._interactive_watch: dict[str, tuple[str, threading.Event]] = {}
        self._state_path = default_state_path()
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(450)
        self._save_timer.timeout.connect(self._save_state)

        self.host_log.connect(self._on_host_log, Qt.QueuedConnection)
        self.host_pr_url.connect(self._on_host_pr_url, Qt.QueuedConnection)
        self.interactive_finished.connect(self._on_interactive_finished, Qt.QueuedConnection)

        self._dashboard_ticker = QTimer(self)
        self._dashboard_ticker.setInterval(1000)
        self._dashboard_ticker.timeout.connect(self._tick_dashboard_elapsed)
        self._dashboard_ticker.start()

        root = GlassRoot()
        self.setCentralWidget(root)

        outer = QVBoxLayout(root)
        outer.setContentsMargins(18, 18, 18, 18)
        outer.setSpacing(14)

        top = GlassCard()
        top_layout = QHBoxLayout(top)
        top_layout.setContentsMargins(14, 12, 14, 12)
        top_layout.setSpacing(10)

        self._btn_home = QToolButton()
        self._btn_home.setText("Home")
        self._btn_home.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self._btn_home.setIcon(self.style().standardIcon(QStyle.SP_DirHomeIcon))
        self._btn_home.clicked.connect(self._show_dashboard)

        self._btn_new = QToolButton()
        self._btn_new.setText("New task")
        self._btn_new.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self._btn_new.setIcon(self.style().standardIcon(QStyle.SP_FileDialogNewFolder))
        self._btn_new.clicked.connect(self._show_new_task)

        self._btn_envs = QToolButton()
        self._btn_envs.setText("Environments")
        self._btn_envs.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self._btn_envs.setIcon(self.style().standardIcon(QStyle.SP_DirIcon))
        self._btn_envs.clicked.connect(self._show_environments)

        self._btn_settings = QToolButton()
        self._btn_settings.setText("Settings")
        self._btn_settings.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self._btn_settings.setIcon(self.style().standardIcon(QStyle.SP_FileDialogDetailedView))
        self._btn_settings.clicked.connect(self._show_settings)

        top_layout.addWidget(self._btn_home)
        top_layout.addWidget(self._btn_new)
        top_layout.addWidget(self._btn_envs)
        top_layout.addWidget(self._btn_settings)
        top_layout.addStretch(1)

        outer.addWidget(top)

        self._dashboard = DashboardPage()
        self._dashboard.task_selected.connect(self._open_task_details)
        self._dashboard.clean_old_requested.connect(self._clean_old_tasks)
        self._dashboard.task_discard_requested.connect(self._discard_task_from_ui)
        self._new_task = NewTaskPage()
        self._new_task.requested_run.connect(self._start_task_from_ui)
        self._new_task.requested_launch.connect(self._start_interactive_task_from_ui)
        self._new_task.environment_changed.connect(self._on_new_task_env_changed)
        self._new_task.back_requested.connect(self._show_dashboard)
        self._details = TaskDetailsPage()
        self._details.back_requested.connect(self._show_dashboard)
        self._details.pr_requested.connect(self._on_task_pr_requested)
        self._envs_page = EnvironmentsPage()
        self._envs_page.back_requested.connect(self._show_dashboard)
        self._envs_page.updated.connect(self._reload_environments, Qt.QueuedConnection)
        self._envs_page.test_preflight_requested.connect(self._on_environment_test_preflight, Qt.QueuedConnection)
        self._settings = SettingsPage()
        self._settings.back_requested.connect(self._show_dashboard)
        self._settings.saved.connect(self._apply_settings, Qt.QueuedConnection)
        self._settings.test_preflight_requested.connect(self._on_settings_test_preflight, Qt.QueuedConnection)
        self._settings.clean_docker_requested.connect(self._on_settings_clean_docker, Qt.QueuedConnection)
        self._settings.clean_git_folders_requested.connect(self._on_settings_clean_git_folders, Qt.QueuedConnection)
        self._settings.clean_all_requested.connect(self._on_settings_clean_all, Qt.QueuedConnection)
        self._cleanup_threads: dict[str, QThread] = {}
        self._cleanup_bridges: dict[str, HostCleanupBridge] = {}
        self._cleanup_pending: dict[str, tuple[str, Callable]] = {}
        self._docker_cleanup_task_id: str | None = None
        self._git_cleanup_task_id: str | None = None
        self._clean_all_queue: list[str] = []

        self._stack = QWidget()
        self._stack_layout = QVBoxLayout(self._stack)
        self._stack_layout.setContentsMargins(0, 0, 0, 0)
        self._stack_layout.setSpacing(0)
        self._stack_layout.addWidget(self._dashboard)
        self._stack_layout.addWidget(self._new_task)
        self._stack_layout.addWidget(self._details)
        self._stack_layout.addWidget(self._envs_page)
        self._stack_layout.addWidget(self._settings)
        self._dashboard.show()
        self._new_task.hide()
        self._details.hide()
        self._envs_page.hide()
        self._settings.hide()
        outer.addWidget(self._stack, 1)

        self._load_state()
        self._apply_window_prefs()
        self._reload_environments()
        self._apply_settings_to_pages()
        self._sync_settings_clean_state()
        self._try_start_queued_tasks()


    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._settings_data["window_w"] = int(self.width())
        self._settings_data["window_h"] = int(self.height())
        if hasattr(self, "_save_timer"):
            self._schedule_save()


    def closeEvent(self, event) -> None:
        try:
            self._save_state()
        except Exception:
            pass
        super().closeEvent(event)
