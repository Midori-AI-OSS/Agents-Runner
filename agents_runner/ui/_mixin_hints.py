"""TYPE_CHECKING-only contracts for mixin classes.

These base classes tell basedpyright what attributes, methods, and signals
each mixin can expect from its runtime host (MainWindow or EnvironmentsPage).
They exist purely for static analysis and add zero runtime overhead.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import threading
    from PySide6.QtCore import QObject, QThread, QTimer, Signal
    from PySide6.QtWidgets import (
        QCheckBox,
        QComboBox,
        QLabel,
        QLineEdit,
        QStackedWidget,
        QToolButton,
        QVBoxLayout,
    )
    from agents_runner.core.agent.watch_state import AgentWatchState
    from agents_runner.environments import Environment
    from agents_runner.environments.model import AgentInstance
    from agents_runner.agent_configs.model import AgentConfig
    from agents_runner.ui.bridges import TaskRunnerBridge
    from agents_runner.ui.graphics import GlassRoot
    from agents_runner.ui.pages.environments_ports import PortsTabWidget
    from agents_runner.ui.pages import (
        DashboardPage,
        EnvironmentsPage,
        NewTaskPage,
        SettingsPage,
        TaskDetailsPage,
        TasksPage,
    )
    from agents_runner.ui.radio import RadioController
    from agents_runner.ui.task_event_proxy import TaskEventProxy
    from agents_runner.ui.task_model import Task


if TYPE_CHECKING:

    class MainWindowHints(QObject):
        _settings_data: dict[str, Any]
        _environments: dict[str, Environment]
        _syncing_environment: bool
        _tasks: dict[str, Task]
        _threads: dict[str, QThread]
        _bridges: dict[str, TaskRunnerBridge]
        _task_event_proxies: dict[str, TaskEventProxy]
        _interactive_prep_threads: dict[str, QThread]
        _interactive_prep_workers: dict[str, Any]
        _interactive_prep_bridges: dict[str, Any]
        _interactive_prep_context: dict[str, dict[str, Any]]
        _run_started_s: dict[str, float]
        _dashboard_log_refresh_s: dict[str, float]
        _interactive_watch: dict[str, tuple[str, threading.Event]]
        _repo_branches_request_id: int
        _repo_branches_request_meta: dict[int, dict[str, Any]]
        _repo_branches_cache: dict[str, list[str]]
        _task_workspace_cleanup_last_check_s: float
        _task_workspace_cleanup_running: bool
        _task_workspace_migration_thread: QThread | None
        _task_workspace_migration_worker: Any | None
        _state_path: str
        _save_timer: QTimer
        _task_event_drain_timer: QTimer
        _watch_states: dict[str, AgentWatchState]
        _dashboard_ticker: QTimer
        _recovery_log_stop: dict[str, threading.Event]
        _finalization_threads: dict[str, threading.Thread]
        _radio_channel_options: list[str]
        _recovery_ticker: QTimer
        _radio_controller: RadioController
        _root: GlassRoot
        _btn_home: QToolButton
        _btn_new: QToolButton
        _btn_envs: QToolButton
        _btn_settings: QToolButton
        _details: TaskDetailsPage
        _dashboard: DashboardPage
        _new_task: NewTaskPage
        _envs_page: EnvironmentsPage
        _settings: SettingsPage
        _tasks_page: TasksPage
        _stack: QStackedWidget
        _agent_selection_round_robin_cursor: dict[str, int]
        _fork_notice_seen: set[str]
        _current_env_name: str

        host_log: Signal
        host_pr_url: Signal
        host_artifacts: Signal
        interactive_finished: Signal
        repo_branches_ready: Signal

        def _schedule_save(self, *_args: object) -> None: ...
        def _save_state(self, *_args: object) -> None: ...
        @staticmethod
        def _should_archive_task(task: Task) -> bool: ...
        def _on_task_log(self, task_id: str, log_line: str) -> None: ...
        def _on_bridge_state(self, task_id: str, state: dict[str, Any]) -> None: ...
        def _on_bridge_log(self, task_id: str, line: str) -> None: ...
        def _on_bridge_done(
            self,
            task_id: str,
            exit_code: int,
            error: object,
            artifacts: list[Any],
            metadata: dict[str, Any] | None = None,
        ) -> None: ...
        def _on_bridge_retry_attempt(self, task_id: str, attempt_number: int, agent: str, delay: float) -> None: ...
        def _on_bridge_agent_switched(self, task_id: str, from_agent: str, to_agent: str) -> None: ...
        @staticmethod
        def _try_sync_container_state(task: Task) -> bool: ...
        def _queue_task_finalization(self, task_id: str, *, reason: str) -> None: ...
        def _show_dashboard(self) -> None: ...
        def _show_tasks(self) -> None: ...
        def _show_task_details(self) -> None: ...
        def _show_environments(self) -> None: ...
        def _show_settings(self) -> None: ...
        def _show_new_task(self) -> None: ...
        def _maybe_auto_navigate_on_task_start(self, *, interactive: bool) -> None: ...
        def _active_environment_id(self) -> str: ...
        def _coerce_agent_override(self, override: Any) -> dict[str, str] | None: ...
        def _resolve_override_agent_runtime(
            self,
            *,
            override: dict[str, str],
            env: Environment | None,
            settings: dict[str, Any] | None = None,
        ) -> tuple[str, str, str, str]: ...
        def _resolve_override_config_dir(
            self,
            *,
            override: dict[str, str],
            env: Environment | None,
            settings: dict[str, Any] | None = None,
        ) -> str | None: ...
        def _select_agent_instance_for_env(
            self,
            *,
            env: Environment,
            settings: dict[str, Any],
            advance_round_robin: bool,
        ) -> tuple[str, str, str, str]: ...
        def _effective_agent_and_config(
            self,
            *,
            env: Environment | None,
            settings: dict[str, Any] | None = None,
            advance_round_robin: bool = False,
        ) -> tuple[str, str, str]: ...
        def _resolve_config_dir_for_agent(
            self,
            *,
            agent_cli: str,
            env: Environment | None,
            settings: dict[str, Any],
        ) -> str: ...
        @staticmethod
        def _find_agent_instance_by_id(
            env: Environment | None,
            agent_id: str,
        ) -> AgentInstance | None: ...
        def _resolve_agent_instance_runtime(
            self,
            inst: Any | None,
            *,
            env: Environment | None,
            settings: dict[str, Any] | None = None,
            agent_configs: dict[str, AgentConfig] | None = None,
            fallback_agent_cli: str = "",
            fallback_config_dir: str = "",
            fallback_cli_flags: str = "",
        ) -> tuple[str, str, str]: ...
        def _load_agent_configs_by_id(self) -> dict[str, AgentConfig]: ...
        def _format_agent_label(
            self,
            inst: Any | None,
            *,
            agent_configs: dict[str, AgentConfig] | None = None,
        ) -> str: ...
        def _new_task_workspace(
            self,
            env: Environment | None,
            task_id: str | None = None,
        ) -> tuple[str, bool, str]: ...
        def _ensure_agent_config_dir(self, agent_cli: str, host_config_dir: str) -> bool: ...
        def _commit_round_robin_selection(
            self,
            *,
            env: Environment | None,
            selected_agent_id: str,
        ) -> None: ...
        def _effective_gpu_enabled(
            self,
            *,
            env: Environment | None,
            settings: dict[str, Any] | None = None,
        ) -> bool: ...
        def _effective_network_host(
            self,
            *,
            env: Environment | None,
            settings: dict[str, Any] | None = None,
        ) -> bool: ...
        def _default_interactive_command(self, agent_cli: str) -> str: ...
        def _effective_opencode_interactive_mode(
            self,
            *,
            env: Environment | None,
            settings: dict[str, Any] | None = None,
        ) -> str: ...
        def _effective_host_config_dir(
            self,
            *,
            agent_cli: str,
            env: Environment | None,
            settings: dict[str, Any] | None = None,
        ) -> str: ...
        def _get_next_agent_info(self, *, env: Environment | None) -> tuple[str, str]: ...
        def _remember_environment_base_branch(self, env: Environment | None, base_branch: str) -> None: ...
        def _refresh_task_rows(self) -> None: ...
        def _refresh_active_environment_repo_branches(
            self,
            *,
            trigger_reason: str,
            show_loading_ui: bool,
            preserve_current_selection: bool,
        ) -> None: ...
        def _populate_environment_pickers(self, *args: object) -> None: ...
        def _update_window_title_from_radio_state(self, state: dict[str, Any]) -> None: ...
        def _apply_active_environment_to_new_task(self) -> None: ...
        def _can_start_new_agent_for_env(self, env_id: str | None) -> bool: ...
        def _actually_start_task(self, task: Task) -> None: ...
        def _start_task_from_ui(
            self,
            prompt: str,
            host_config_dir: str,
            env_id: str,
            base_branch: str,
            pr_context: dict[str, object] | None = None,
            agent_override: dict[str, str] | None = None,
        ) -> str | None: ...
        def _reconcile_tasks_after_restart(self) -> None: ...
        def _try_start_queued_tasks(self) -> None: ...
        def _update_task_ui(self, task: Task) -> None: ...
        def _force_remove_container(self, container_id: str) -> None: ...
        def _finalize_gh_management_worker(
            self,
            task_id: str,
            repo_root: str,
            branch: str,
            base_branch: str,
            prompt_text: str,
            task_token: str,
            use_gh: bool,
            pr_metadata_path: str | None = None,
            agent_cli: str = "",
            is_override: bool = False,
        ) -> None: ...
        def _start_artifact_finalization(self, task: Task) -> None: ...
        def _compute_cross_agent_config_mounts(
            self,
            *,
            env: Environment | None,
            primary_agent_cli: str,
            primary_config_dir: str,
            settings: dict[str, Any] | None = None,
        ) -> list[str]: ...
        def _sync_radio_controller_from_settings(
            self,
            *,
            user_initiated: bool,
            previous_enabled: bool | None = None,
        ) -> None: ...
        def _refresh_new_task_agent_info(self) -> None: ...
        def _environment_list(self) -> list[Environment]: ...
        def _environment_effective_workdir(
            self,
            env: Environment | None,
            fallback: str,
            *,
            settings: dict[str, Any] | None = None,
        ) -> str: ...
        def _user_environment_map(self) -> dict[str, Environment]: ...
        @staticmethod
        def _is_internal_environment_id(env_id: str) -> bool: ...
        def _refresh_radio_channel_options(self, *, disable_on_failure: bool) -> None: ...
else:

    class MainWindowHints:
        pass


if TYPE_CHECKING:

    class EnvironmentsPageHints(QObject):
        _environments: dict[str, Environment]
        _current_env_id: str | None
        _settings_data: dict[str, Any]
        _suppress_autosave: bool
        _autosave_timer: QTimer
        _advanced_autosave_timer: QTimer

        _workspace_type_combo: QComboBox
        _workspace_target: QLineEdit
        _gh_use_host_cli: QCheckBox
        _gh_management_browse: QToolButton
        _name: QLineEdit
        _max_agents_running: QLineEdit
        _color: QComboBox
        _env_select: QComboBox
        _headless_desktop_enabled: QCheckBox
        _cache_desktop_build: QCheckBox
        _container_caching_enabled: QCheckBox
        _use_cross_agents: QCheckBox
        _gh_context_enabled: QCheckBox
        _github_polling_enabled: QCheckBox
        _agentsnova_trusted_mode: QComboBox
        _agentsnova_auto_review_mode: QComboBox
        _agentsnova_auto_reactions_mode: QComboBox
        _agentsnova_marker_comment_mode: QComboBox
        _interactive_pr_no_prompt_mode: QComboBox
        _interactive_pr_prompt_enabled: QCheckBox
        _setup_agents_missing_prompt_enabled: QCheckBox
        _interactive_pull_before_run_enabled: QCheckBox
        _gh_branch_work_mode: QComboBox
        _gh_task_branch_naming_style: QComboBox
        _gh_task_branch_custom_template: QLineEdit
        _gpu_override_mode: QComboBox
        _opencode_interactive_mode: QComboBox
        _cache_system_preflight_enabled: QCheckBox
        _cache_settings_preflight_enabled: QCheckBox
        _env_vars_tab: Any
        _mounts_tab: Any
        _ports_tab: PortsTabWidget
        _prompts_tab: Any
        _agents_tab: Any
        _agentsnova_trusted_users_env: Any

        _pane_specs: list[Any]
        _active_pane_key: str
        _nav_buttons: dict[str, QToolButton]
        _pane_index_by_key: dict[str, int]
        _page_stack: QStackedWidget
        _compact_nav: QComboBox
        _nav_scroll: Any
        _compact_mode: bool
        _pane_animation: Any | None
        _pane_rest_pos: Any | None

        updated: Signal
        test_preflight_requested: Signal
        back_requested: Signal

        def _sync_workspace_controls(self, *args: object) -> None: ...
        def _issue_294_environment_values(self) -> dict[str, Any]: ...
        def _draft_environment_from_form(self, *args: object) -> Environment | None: ...
        def try_autosave(
            self,
            *,
            preferred_env_id: str | None = None,
            show_validation_errors: bool = True,
        ) -> bool: ...
        def _queue_debounced_autosave(self, *args: object) -> None: ...
        def _queue_advanced_autosave(self, *args: object) -> None: ...
        def _emit_autosave(self) -> None: ...
        def _default_pane_specs(self) -> list[Any]: ...
        def _apply_environment_tints(self) -> None: ...
        def _on_headless_desktop_toggled(self, state: int) -> None: ...
        def _on_container_caching_toggled(self, state: int) -> None: ...
        def _on_use_cross_agents_toggled(self, state: int) -> None: ...
        def _sync_interactive_pr_controls(self) -> None: ...
        def _sync_github_branch_naming_controls(self) -> None: ...
        def _on_ports_changed(self) -> None: ...
        def _on_prompts_changed(self) -> None: ...
        def _on_agents_changed(self) -> None: ...
        def _on_setup_environment_github_defaults(self) -> None: ...
        def _navigate_to_pane(self, key: str, *, user_initiated: bool) -> None: ...
        def _set_active_navigation(self, key: str) -> None: ...
        def _set_current_pane(self, key: str, *, animate: bool) -> None: ...
        def _animate_stack(self, *, forward: bool) -> None: ...
        def _build_navigation(self, nav_layout: QVBoxLayout) -> None: ...
        def _current_environment(self) -> Environment | None: ...
else:

    class EnvironmentsPageHints:
        pass


if TYPE_CHECKING:

    class SettingsPageHints(QObject):
        _github_poll_interval_s: QLineEdit
        _github_poll_rate_warning_label: QLabel
        _github_polling_enabled: QCheckBox

        def _refresh_github_poll_rate_warning(self, *_args: object) -> None: ...
        def _queue_debounced_autosave(self, *_args: object) -> None: ...
else:

    class SettingsPageHints:
        pass
