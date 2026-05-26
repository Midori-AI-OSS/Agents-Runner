from __future__ import annotations

import logging
import os
import threading

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtCore import QThread
from PySide6.QtWidgets import QMessageBox
from PySide6.QtWidgets import QProgressDialog

from agents_runner.agent_cli import normalize_agent
from agents_runner.agent_cli import container_config_dir
from agents_runner.agent_cli import additional_config_mounts
from agents_runner.agent_cli import available_agents
from agents_runner.agent_cli import default_host_config_dir
from agents_runner.agent_labels import format_agent_ui_label
from agents_runner.agent_systems import get_agent_system
from agents_runner.ui.radio import RadioController
from agents_runner.ui.utils import looks_like_agent_help_command
from agents_runner.environments import Environment
from agents_runner.environments.model import normalize_gpu_override_mode
from agents_runner.environments.model import normalize_opencode_interactive_mode
from agents_runner.environments.model import normalize_opencode_interactive_override
from agents_runner.environments.task_workspaces import TASK_WORKSPACE_LOCATION_APP_DATA
from agents_runner.environments.task_workspaces import (
    TASK_WORKSPACE_LOCATION_SCRATCH_DRIVE,
)
from agents_runner.environments.task_workspaces import normalize_task_workspace_settings
from agents_runner.environments.task_workspaces import task_workspace_path
from agents_runner.persistence import load_all_done_task_payloads
from agents_runner.persistence import save_task_payload
from agents_runner.persistence import serialize_task
from agents_runner.gh.automation_policy import normalize_default_marker_comment_mode
from agents_runner.ui.task_workspace_migration import TaskWorkspaceMigrationRecord
from agents_runner.ui.task_workspace_migration import TaskWorkspaceMigrationWorker

logger = logging.getLogger(__name__)


class MainWindowSettingsMixin:
    _REMOVED_IDE_SETTINGS_KEYS = (
        "ide_auto_mounts_enabled",
        "ide_system_default",
        "ide_display_target_default",
        "ide_display_target",
        "ide_novnc_auto_open_enabled",
        "ide_novnc_auto_open_mode",
    )
    _REMOVED_LEGACY_SETTINGS_KEYS = (
        "host_codex_dir",
        "host_claude_dir",
        "host_copilot_dir",
        "host_gemini_dir",
        "agent_interactive_commands",
        "interactive_command",
        "interactive_command_claude",
        "interactive_command_copilot",
        "interactive_command_gemini",
    )

    def _apply_settings_to_pages(self) -> None:
        if not self._settings.isVisible():
            self._settings.set_settings(self._settings_data)
        if hasattr(self._settings, "set_task_workspace_migration_blocked"):
            self._settings.set_task_workspace_migration_blocked(
                self._has_active_cloned_task_workspaces()
            )
        self._envs_page.set_settings_data(
            self._settings_data
        )  # Pass settings to environments page
        if hasattr(self, "_tasks_page"):
            self._tasks_page.set_settings_data(self._settings_data)
        self._apply_active_environment_to_new_task()

        # Apply spellcheck setting to new task page
        spellcheck_enabled = bool(self._settings_data.get("spellcheck_enabled", True))
        self._new_task.set_spellcheck_enabled(spellcheck_enabled)
        self._new_task.set_stt_mode("offline")

    def _has_active_cloned_task_workspaces(self) -> bool:
        for task in getattr(self, "_tasks", {}).values():
            if str(getattr(task, "workspace_type", "") or "") != "cloned":
                continue
            status = str(getattr(task, "status", "") or "").strip().lower()
            finalization = (
                str(getattr(task, "finalization_state", "") or "").strip().lower()
            )
            if task.is_active() or status in {"queued", "running", "finalizing"}:
                return True
            if finalization in {"pending", "running"} and not (
                task.is_done() or task.is_failed()
            ):
                return True
        return False

    def _on_move_task_workspaces_requested(self, force: bool) -> None:
        if self._has_active_cloned_task_workspaces() and not force:
            QMessageBox.information(
                self,
                "Active tasks",
                "Active tasks must finish before task workspaces can be moved.",
            )
            self._apply_settings_to_pages()
            return

        if force and self._has_active_cloned_task_workspaces():
            if (
                QMessageBox.question(
                    self,
                    "Force migration?",
                    "Force migration will stop active cloned tasks before moving workspaces.",
                )
                != QMessageBox.StandardButton.Yes
            ):
                return
            self._force_stop_cloned_tasks_for_migration()

        target_location = str(
            self._settings_data.get("task_workspace_location") or "app_data"
        )
        target_location = (
            TASK_WORKSPACE_LOCATION_SCRATCH_DRIVE
            if target_location == TASK_WORKSPACE_LOCATION_SCRATCH_DRIVE
            else TASK_WORKSPACE_LOCATION_APP_DATA
        )
        source_location = (
            TASK_WORKSPACE_LOCATION_APP_DATA
            if target_location == TASK_WORKSPACE_LOCATION_SCRATCH_DRIVE
            else TASK_WORKSPACE_LOCATION_SCRATCH_DRIVE
        )
        records = self._migration_records()
        if not records:
            QMessageBox.information(
                self,
                "No workspaces",
                "No cloned task workspaces were found to move.",
            )
            return
        self._start_task_workspace_migration(
            records=records,
            source_location=source_location,
            target_location=target_location,
        )

    def _force_stop_cloned_tasks_for_migration(self) -> None:
        for task_id, task in list(getattr(self, "_tasks", {}).items()):
            if str(getattr(task, "workspace_type", "") or "") != "cloned":
                continue
            if not task.is_active():
                continue
            bridge = getattr(self, "_bridges", {}).get(task_id)
            if bridge is not None:
                try:
                    bridge.request_user_cancel()
                except Exception:
                    pass
            prep_worker = getattr(self, "_interactive_prep_workers", {}).get(task_id)
            if prep_worker is not None:
                try:
                    prep_worker.request_stop()
                except Exception:
                    pass
            watch = getattr(self, "_interactive_watch", {}).get(task_id)
            if watch is not None:
                try:
                    _label, stop = watch
                    stop.set()
                except Exception:
                    pass
            container_id = str(getattr(task, "container_id", "") or "").strip()
            if container_id:
                threading.Thread(
                    target=self._force_remove_container,
                    args=(container_id,),
                    daemon=True,
                ).start()
            task.status = "cancelled"
            task.finalization_state = "done"
            task.finalization_error = ""
            self._update_task_ui(task)
        self._schedule_save()

    def _migration_records(self) -> list[TaskWorkspaceMigrationRecord]:
        records: list[TaskWorkspaceMigrationRecord] = []
        seen: set[tuple[str, str]] = set()

        def _add(payload: dict[str, object]) -> None:
            if str(payload.get("workspace_type") or "").strip() != "cloned":
                return
            task_id = str(payload.get("task_id") or "").strip()
            env_id = str(payload.get("environment_id") or "").strip()
            if not task_id or not env_id:
                return
            key = (env_id, task_id)
            if key in seen:
                return
            seen.add(key)
            records.append(
                TaskWorkspaceMigrationRecord(
                    task_id=task_id,
                    environment_id=env_id,
                )
            )

        for task in getattr(self, "_tasks", {}).values():
            _add(
                {
                    "task_id": getattr(task, "task_id", ""),
                    "environment_id": getattr(task, "environment_id", ""),
                    "workspace_type": getattr(task, "workspace_type", ""),
                }
            )
        for payload in load_all_done_task_payloads(self._state_path):
            _add(payload)
        return records

    def _start_task_workspace_migration(
        self,
        *,
        records: list[TaskWorkspaceMigrationRecord],
        source_location: str,
        target_location: str,
    ) -> None:
        progress = QProgressDialog(
            "Preparing migration...", "Close", 0, len(records), self
        )
        progress.setWindowTitle("Move all tasks")
        progress.setWindowModality(Qt.WindowModality.ApplicationModal)
        progress.setCancelButton(None)
        progress.setMinimumDuration(0)
        progress.setValue(0)
        progress.show()

        thread = QThread(self)
        worker = TaskWorkspaceMigrationWorker(
            records=records,
            data_dir=os.path.dirname(self._state_path),
            source_location=source_location,
            destination_location=target_location,
        )
        worker.moveToThread(thread)

        def _on_progress(done: int, total: int, task_id: str, eta: str) -> None:
            progress.setMaximum(max(1, int(total)))
            progress.setValue(max(0, int(done)))
            progress.setLabelText(
                f"Moving {done}/{total}\nCurrent task: {task_id or 'Preparing'}\n{eta}"
            )

        def _on_finished(
            moved: int,
            skipped: int,
            failed: int,
            failures: object,
            moved_records: object,
        ) -> None:
            progress.setValue(progress.maximum())
            self._apply_migrated_workspace_paths(moved_records, target_location)
            detail = f"Moved: {moved}\nSkipped: {skipped}\nFailed: {failed}"
            if failed and isinstance(failures, list):
                detail = f"{detail}\n\n" + "\n".join(str(item) for item in failures[:5])
            progress.setLabelText(detail)
            QMessageBox.information(self, "Move all tasks", detail)
            thread.quit()
            worker.deleteLater()
            thread.deleteLater()
            self._task_workspace_migration_thread = None
            self._task_workspace_migration_worker = None
            self._apply_settings_to_pages()

        worker.progress.connect(_on_progress)
        worker.finished.connect(_on_finished)
        thread.started.connect(worker.run)
        self._task_workspace_migration_thread = thread
        self._task_workspace_migration_worker = worker
        thread.start()

    def _apply_migrated_workspace_paths(
        self, moved_records: object, target_location: str
    ) -> None:
        records = moved_records if isinstance(moved_records, list) else []
        moved_by_task = {
            str(getattr(record, "task_id", "") or ""): str(
                getattr(record, "destination", "") or ""
            )
            for record in records
        }
        if not moved_by_task:
            return
        for task_id, destination in moved_by_task.items():
            task = self._tasks.get(task_id)
            if task is None:
                continue
            task.host_workdir = destination
            if str(getattr(task, "workspace_type", "") or "") == "cloned":
                task.gh_repo_root = destination
            save_task_payload(
                self._state_path,
                serialize_task(task),
                archived=self._should_archive_task(task),
            )

        for payload in load_all_done_task_payloads(self._state_path):
            task_id = str(payload.get("task_id") or "").strip()
            destination = moved_by_task.get(task_id)
            if not destination:
                continue
            payload["host_workdir"] = destination
            payload["gh_repo_root"] = destination
            save_task_payload(self._state_path, payload, archived=True)

        for payload in load_all_done_task_payloads(self._state_path):
            task_id = str(payload.get("task_id") or "").strip()
            if task_id in moved_by_task:
                continue
            env_id = str(payload.get("environment_id") or "").strip()
            if not task_id or not env_id:
                continue
            destination = task_workspace_path(
                env_id,
                task_id=task_id,
                data_dir=os.path.dirname(self._state_path),
                location=target_location,
            )
            if os.path.isdir(destination):
                payload["host_workdir"] = destination
                payload["gh_repo_root"] = destination
                save_task_payload(self._state_path, payload, archived=True)
        self._schedule_save()

    def _apply_settings(self, settings: dict[str, Any]) -> None:
        previous_radio_enabled = bool(self._settings_data.get("radio_enabled") or False)
        merged = dict(self._settings_data)
        merged.update(settings or {})
        merged.pop("stt_mode", None)
        for key in self._REMOVED_IDE_SETTINGS_KEYS:
            merged.pop(key, None)
        merged["use"] = normalize_agent(str(merged.get("use") or "codex"))
        if merged["use"] not in set(available_agents(include_internal=False)):
            merged["use"] = "codex"

        shell_value = str(merged.get("shell") or "bash").lower()
        if shell_value not in {"bash", "sh", "zsh", "fish", "tmux"}:
            shell_value = "bash"
        merged["shell"] = shell_value

        merged["preflight_enabled"] = bool(merged.get("preflight_enabled") or False)
        merged["preflight_script"] = str(merged.get("preflight_script") or "")
        merged["interactive_terminal_id"] = str(
            merged.get("interactive_terminal_id") or ""
        ).strip()
        for key in self._REMOVED_LEGACY_SETTINGS_KEYS:
            merged.pop(key, None)
        merged["append_pixelarch_context"] = bool(
            merged.get("append_pixelarch_context") or False
        )
        merged["github_workroom_prefer_browser"] = bool(
            merged.get("github_workroom_prefer_browser") or False
        )
        confirmation_mode = (
            str(merged.get("github_write_confirmation_mode") or "always")
            .strip()
            .lower()
        )
        if confirmation_mode not in {"always", "destructive_only", "never"}:
            confirmation_mode = "always"
        merged["github_write_confirmation_mode"] = confirmation_mode
        merged["agentsnova_auto_review_enabled"] = bool(
            merged.get("agentsnova_auto_review_enabled", True)
        )
        merged["agentsnova_auto_marker_comments_mode"] = (
            normalize_default_marker_comment_mode(
                merged.get(
                    "agentsnova_auto_marker_comments_mode",
                    merged.get("agentsnova_auto_marker_comments_enabled", True),
                )
            )
        )
        merged.pop("agentsnova_auto_marker_comments_enabled", None)
        merged["agentsnova_auto_reactions_enabled"] = bool(
            merged.get("agentsnova_auto_reactions_enabled", True)
        )
        try:
            merged["github_poll_interval_s"] = max(
                5, int(merged.get("github_poll_interval_s", 30))
            )
        except Exception:
            merged["github_poll_interval_s"] = 30
        merged["github_polling_enabled"] = bool(
            merged.get("github_polling_enabled") or False
        )
        try:
            merged["github_poll_startup_delay_s"] = max(
                0, int(merged.get("github_poll_startup_delay_s", 35))
            )
        except Exception:
            merged["github_poll_startup_delay_s"] = 35
        trusted_users_raw = merged.get("agentsnova_trusted_users_global")
        trusted_users_rows = (
            trusted_users_raw if isinstance(trusted_users_raw, list) else []
        )
        trusted_users: list[str] = []
        seen_trusted_users: set[str] = set()
        for row in trusted_users_rows:
            username = str(row or "").strip().lstrip("@").lower()
            if not username or username in seen_trusted_users:
                continue
            trusted_users.append(username)
            seen_trusted_users.add(username)
        merged["agentsnova_trusted_users_global"] = trusted_users
        merged["agentsnova_review_guard_mode"] = (
            str(merged.get("agentsnova_review_guard_mode") or "reaction").strip()
            or "reaction"
        )
        merged["headless_desktop_enabled"] = bool(
            merged.get("headless_desktop_enabled") or False
        )
        merged["gpu_enabled"] = bool(merged.get("gpu_enabled") or False)
        merged["opencode_interactive_mode"] = normalize_opencode_interactive_mode(
            str(merged.get("opencode_interactive_mode") or "terminal")
        )
        merged["popup_theme_animation_enabled"] = bool(
            merged.get("popup_theme_animation_enabled", True)
        )
        merged["auto_navigate_on_run_agent_start"] = bool(
            merged.get("auto_navigate_on_run_agent_start") or False
        )
        merged["auto_navigate_on_run_interactive_start"] = bool(
            merged.get("auto_navigate_on_run_interactive_start") or False
        )
        merged["radio_enabled"] = bool(merged.get("radio_enabled") or False)
        merged["radio_autostart"] = bool(merged.get("radio_autostart") or False)
        merged["radio_channel"] = RadioController.normalize_channel(
            merged.get("radio_channel")
        )
        merged["radio_quality"] = RadioController.normalize_quality(
            merged.get("radio_quality")
        )
        merged["radio_volume"] = RadioController.clamp_volume(
            merged.get("radio_volume")
        )
        merged["radio_loudness_boost_enabled"] = bool(
            merged.get("radio_loudness_boost_enabled") or False
        )
        merged["radio_loudness_boost_factor"] = (
            RadioController.normalize_loudness_boost_factor(
                merged.get("radio_loudness_boost_factor")
            )
        )
        merged = normalize_task_workspace_settings(merged)
        try:
            from agents_runner.ui.graphics import normalize_ui_theme_name

            merged["ui_theme"] = normalize_ui_theme_name(
                merged.get("ui_theme"), allow_auto=True
            )
        except Exception:
            merged["ui_theme"] = "auto"

        try:
            merged["max_agents_running"] = int(
                str(merged.get("max_agents_running", -1)).strip()
            )
        except Exception:
            merged["max_agents_running"] = -1
        self._settings_data = merged
        self._sync_radio_controller_from_settings(
            user_initiated=True,
            previous_enabled=previous_radio_enabled,
        )
        self._apply_settings_to_pages()
        self._schedule_save()

    def _plugin_default_interactive_command(self, agent_cli: str) -> str:
        agent_cli = str(agent_cli or "").strip().lower()
        if not agent_cli or agent_cli not in set(
            available_agents(include_internal=False)
        ):
            return ""
        try:
            plugin = get_agent_system(agent_cli)
        except Exception:
            return ""
        return str(plugin.default_interactive_command() or "").strip()

    def _default_interactive_command(self, agent_cli: str) -> str:
        agent_cli = str(agent_cli or "").strip().lower()
        if not agent_cli or agent_cli not in set(
            available_agents(include_internal=False)
        ):
            return ""
        return self._plugin_default_interactive_command(agent_cli)

    @staticmethod
    def _is_agent_help_interactive_launch(prompt: str, command: str) -> bool:
        prompt = str(prompt or "").strip().lower()
        if prompt.startswith("get agent help"):
            return True
        return looks_like_agent_help_command(command)

    def _resolve_config_dir_for_agent(
        self,
        *,
        agent_cli: str,
        env: Environment | None,
        settings: dict[str, object],
    ) -> str:
        """Resolve a host config directory for an agent CLI.

        Precedence:
        1. Plugin default host config dir
        """
        del env, settings
        agent_cli = str(agent_cli or "").strip().lower()
        if agent_cli not in set(available_agents(include_internal=False)):
            return ""
        return os.path.expanduser(default_host_config_dir(agent_cli))

    def _select_agent_instance_for_env(
        self,
        *,
        env: Environment,
        settings: dict[str, object],
        advance_round_robin: bool,
    ) -> tuple[str, str, str]:
        agents = list(getattr(env.agent_selection, "agents", []) or [])
        if not agents:
            agent_cli = normalize_agent(str(settings.get("use") or "codex"))
            config_dir = self._resolve_config_dir_for_agent(
                agent_cli=agent_cli, env=env, settings=settings
            )
            return agent_cli, config_dir, ""

        mode = (
            str(getattr(env.agent_selection, "selection_mode", "") or "round-robin")
            .strip()
            .lower()
        )
        env_id = str(getattr(env, "env_id", "") or "")

        if not hasattr(self, "_agent_selection_round_robin_cursor"):
            self._agent_selection_round_robin_cursor = {}

        chosen = agents[0]
        if mode == "round-robin":
            cursor = int(
                getattr(self, "_agent_selection_round_robin_cursor", {}).get(env_id, 0)
            )
            idx = cursor % len(agents)
            chosen = agents[idx]
            if advance_round_robin:
                getattr(self, "_agent_selection_round_robin_cursor", {})[env_id] = (
                    idx + 1
                )
        elif mode == "least-used":
            counts: dict[str, int] = {}
            tasks = getattr(self, "_tasks", {}) or {}
            for task in tasks.values():
                if getattr(task, "environment_id", "") != env_id:
                    continue
                if not getattr(task, "is_active", lambda: False)():
                    continue
                agent_instance_id = str(
                    getattr(task, "agent_instance_id", "") or ""
                ).strip()
                if not agent_instance_id:
                    continue
                counts[agent_instance_id] = counts.get(agent_instance_id, 0) + 1

            def _score(inst: object) -> tuple[int, int]:
                inst_id = str(getattr(inst, "agent_id", "") or "").strip()
                return counts.get(inst_id, 0), agents.index(inst)

            chosen = min(agents, key=_score)
        elif mode == "pinned":
            pinned_id = str(
                getattr(env.agent_selection, "pinned_agent_id", "") or ""
            ).strip()
            if pinned_id:
                pinned_lower = pinned_id.lower()
                pinned_inst = next(
                    (
                        inst
                        for inst in agents
                        if str(getattr(inst, "agent_id", "") or "").strip() == pinned_id
                    ),
                    None,
                ) or next(
                    (
                        inst
                        for inst in agents
                        if str(getattr(inst, "agent_id", "") or "").strip().lower()
                        == pinned_lower
                    ),
                    None,
                )
                if pinned_inst is not None:
                    chosen = pinned_inst

        agent_cli = normalize_agent(str(getattr(chosen, "agent_cli", "") or "codex"))
        agent_id = str(getattr(chosen, "agent_id", "") or "").strip()

        config_dir = os.path.expanduser(
            str(getattr(chosen, "config_dir", "") or "").strip()
        )
        if not config_dir:
            config_dir = self._resolve_config_dir_for_agent(
                agent_cli=agent_cli, env=env, settings=settings
            )

        return agent_cli, config_dir, agent_id

    def _commit_round_robin_selection(
        self,
        *,
        env: Environment | None,
        selected_agent_id: str,
    ) -> None:
        if (
            env is None
            or not env.agent_selection
            or not getattr(env.agent_selection, "agents", None)
        ):
            return

        mode = (
            str(getattr(env.agent_selection, "selection_mode", "") or "round-robin")
            .strip()
            .lower()
        )
        if mode != "round-robin":
            return

        agents = list(env.agent_selection.agents or [])
        if not agents:
            return

        env_id = str(getattr(env, "env_id", "") or "").strip()
        if not env_id:
            return

        if not hasattr(self, "_agent_selection_round_robin_cursor"):
            self._agent_selection_round_robin_cursor = {}
        cursor_map = getattr(self, "_agent_selection_round_robin_cursor", {})

        selected_id = str(selected_agent_id or "").strip()
        selected_idx: int | None = None
        if selected_id:
            selected_lower = selected_id.lower()
            for idx, inst in enumerate(agents):
                inst_id = str(getattr(inst, "agent_id", "") or "").strip()
                if inst_id == selected_id or inst_id.lower() == selected_lower:
                    selected_idx = idx
                    break

        if selected_idx is None:
            cursor = int(cursor_map.get(env_id, 0))
            selected_idx = cursor % len(agents)

        cursor_map[env_id] = selected_idx + 1

    def _refresh_new_task_agent_info(self) -> None:
        if not hasattr(self, "_new_task"):
            return
        if not hasattr(self._new_task, "set_agent_info"):
            return
        env = self._environments.get(self._active_environment_id())
        current_agent, next_agent = self._get_next_agent_info(env=env)
        self._new_task.set_agent_info(agent=current_agent, next_agent=next_agent)

    def _effective_agent_and_config(
        self,
        *,
        env: Environment | None,
        settings: dict[str, object] | None = None,
        advance_round_robin: bool = False,
    ) -> tuple[str, str]:
        """Return the effective ``(agent_cli, config_dir)`` for a launch.

        Agent and config directory selection follows this precedence:

        1. Environment ``agent_selection`` override

           * If ``env`` is provided and ``env.agent_selection.agents`` is non-empty,
             an agent instance is selected based on ``selection_mode``.
           * If the selected instance has an explicit ``config_dir``, that path is
             used; otherwise it falls back to that plugin's default config dir.

        2. Global UI settings

           * If no environment-specific agent is found, the agent is taken from
            ``settings["use"]`` (defaulting to ``"codex"``) and normalized via
             :func:`normalize_agent`.
           * The config directory is then derived from that plugin's default host
             config directory.

        The returned ``config_dir`` is always a string with ``~`` expanded via
        :func:`os.path.expanduser`.

        Args:
            env: Optional environment with potential agent overrides
            settings: Optional settings dict; uses ``self._settings_data`` if None

        Returns:
            A tuple of (agent_cli, config_dir) where agent_cli is normalized
        """
        settings = settings or self._settings_data
        if env and env.agent_selection and getattr(env.agent_selection, "agents", None):
            agent_cli, config_dir, _agent_id = self._select_agent_instance_for_env(
                env=env,
                settings=settings,
                advance_round_robin=advance_round_robin,
            )
            return agent_cli, config_dir

        agent_cli = normalize_agent(str(settings.get("use") or "codex"))
        config_dir = self._resolve_config_dir_for_agent(
            agent_cli=agent_cli, env=env, settings=settings
        )
        return agent_cli, config_dir

    def _effective_host_config_dir(
        self,
        *,
        agent_cli: str,
        env: Environment | None,
        settings: dict[str, object] | None = None,
    ) -> str:
        """Return the effective host config directory for the given agent CLI.

        The directory is resolved using the following precedence order:

        1. If an ``env`` is provided and it has an ``agent_selection`` entry with an
           agent instance matching this (normalized) ``agent_cli`` and a non-empty
           ``config_dir``, that directory is used.
        2. Otherwise, the plugin default for that agent is used.

        The returned path is normalized with :func:`os.path.expanduser`.

        Args:
            agent_cli: The agent CLI name (will be normalized)
            env: Optional environment with potential overrides
            settings: Optional settings dict; uses ``self._settings_data`` if None

        Returns:
            The resolved config directory path (with ~ expanded)
        """
        agent_cli = str(agent_cli or "").strip().lower()
        if agent_cli not in set(available_agents(include_internal=False)):
            return ""
        settings = settings or self._settings_data

        # Use helper method to resolve config directory
        return self._resolve_config_dir_for_agent(
            agent_cli=agent_cli,
            env=env,
            settings=settings,
        )

    def _coerce_agent_override(self, override: object) -> dict[str, str] | None:
        if not isinstance(override, dict):
            return None
        agent_cli = str(override.get("agent_cli") or "").strip().lower()
        if agent_cli not in set(available_agents(include_internal=False)):
            agent_cli = ""
        return {
            "source": str(override.get("source") or ""),
            "env_id": str(override.get("env_id") or ""),
            "agent_cli": agent_cli,
            "agent_id": str(override.get("agent_id") or ""),
            "config_dir": str(override.get("config_dir") or ""),
            "cli_flags": str(override.get("cli_flags") or ""),
            "mode": str(override.get("mode") or ""),
            "shell": str(override.get("shell") or ""),
        }

    def _effective_gpu_enabled(
        self,
        *,
        env: Environment | None,
        settings: dict[str, object] | None = None,
    ) -> bool:
        settings_data = settings or self._settings_data
        global_enabled = bool(settings_data.get("gpu_enabled") or False)
        if env is None:
            return global_enabled
        mode = normalize_gpu_override_mode(
            str(getattr(env, "gpu_override_mode", "inherit") or "inherit")
        )
        if mode == "enabled":
            return True
        if mode == "disabled":
            return False
        return global_enabled

    def _effective_opencode_interactive_mode(
        self,
        *,
        env: Environment | None,
        settings: dict[str, object] | None = None,
    ) -> str:
        settings_data = settings or self._settings_data
        global_mode = normalize_opencode_interactive_mode(
            str(settings_data.get("opencode_interactive_mode") or "terminal")
        )
        if env is None:
            return global_mode
        override = normalize_opencode_interactive_override(
            str(getattr(env, "opencode_interactive_mode", "inherit") or "inherit")
        )
        if override == "inherit":
            return global_mode
        return override

    def _resolve_override_config_dir(
        self,
        *,
        override: dict[str, str],
        env: Environment | None,
        settings: dict[str, object] | None = None,
    ) -> str:
        config_dir = str(override.get("config_dir") or "").strip()
        if config_dir:
            return os.path.expanduser(config_dir)

        agent_cli = str(override.get("agent_cli") or "").strip().lower()
        if agent_cli not in set(available_agents(include_internal=False)):
            return ""
        if not agent_cli:
            return ""

        source = str(override.get("source") or "")
        if source == "env":
            return self._resolve_config_dir_for_agent(
                agent_cli=agent_cli,
                env=None,
                settings=settings or self._settings_data,
            )
        return self._resolve_config_dir_for_agent(
            agent_cli=agent_cli,
            env=env,
            settings=settings or self._settings_data,
        )

    def _ensure_agent_config_dir(self, agent_cli: str, host_config_dir: str) -> bool:
        agent_cli = str(agent_cli or "").strip().lower()
        host_config_dir = os.path.expanduser(str(host_config_dir or "").strip())
        if not host_config_dir:
            agent_label = agent_cli
            try:
                agent_label = (
                    str(
                        getattr(get_agent_system(agent_cli), "display_name", "") or ""
                    ).strip()
                    or agent_cli
                )
            except Exception:
                pass
            agent_label = (
                agent_label[0].upper() + agent_label[1:] if agent_label else "Agent"
            )
            QMessageBox.warning(
                self,
                "Missing config folder",
                f"{agent_label} needs a valid config folder. Leave the environment override blank to use the plugin default, or set an explicit per-environment override.",
            )
            return False
        if os.path.exists(host_config_dir) and not os.path.isdir(host_config_dir):
            QMessageBox.warning(
                self, "Invalid config folder", "Config folder path is not a directory."
            )
            return False
        try:
            os.makedirs(host_config_dir, exist_ok=True)
        except Exception as exc:
            QMessageBox.warning(self, "Invalid config folder", str(exc))
            return False
        return True

    def _get_next_agent_info(self, *, env: Environment | None) -> tuple[str, str]:
        """Return (current, next) labels for Run button tooltips."""
        agent_cli, _ = self._effective_agent_and_config(env=env)

        if (
            not env
            or not env.agent_selection
            or not getattr(env.agent_selection, "agents", None)
        ):
            return agent_cli, ""

        agents = list(env.agent_selection.agents or [])
        if len(agents) <= 1:
            inst = agents[0] if agents else None
            if inst is None:
                return agent_cli, ""
            return self._format_agent_label(inst), ""

        mode = (
            str(getattr(env.agent_selection, "selection_mode", "") or "round-robin")
            .strip()
            .lower()
        )
        env_id = str(getattr(env, "env_id", "") or "")

        if mode == "pinned":
            pinned_id = str(
                getattr(env.agent_selection, "pinned_agent_id", "") or ""
            ).strip()
            if pinned_id:
                pinned_lower = pinned_id.lower()
                pinned_inst = next(
                    (
                        inst
                        for inst in agents
                        if str(getattr(inst, "agent_id", "") or "").strip() == pinned_id
                    ),
                    None,
                ) or next(
                    (
                        inst
                        for inst in agents
                        if str(getattr(inst, "agent_id", "") or "").strip().lower()
                        == pinned_lower
                    ),
                    None,
                )
                if pinned_inst is not None:
                    return self._format_agent_label(pinned_inst), ""
            current = agents[0]
            return self._format_agent_label(current), ""

        cursor_map = (
            getattr(self, "_agent_selection_round_robin_cursor", {})
            if hasattr(self, "_agent_selection_round_robin_cursor")
            else {}
        )
        cursor = int(cursor_map.get(env_id, 0))
        current_idx = 0 if mode != "round-robin" else (cursor % len(agents))
        current = agents[current_idx]

        if mode == "fallback":
            fallbacks = dict(getattr(env.agent_selection, "agent_fallbacks", {}) or {})
            wanted_id = str(
                fallbacks.get(str(getattr(current, "agent_id", "") or "").strip(), "")
                or ""
            ).strip()
            next_inst = next(
                (
                    a
                    for a in agents
                    if str(getattr(a, "agent_id", "") or "").strip() == wanted_id
                ),
                None,
            )
            next_label = self._format_agent_label(next_inst) if next_inst else ""
            if next_label:
                next_label = f"Fallback: {next_label}"
            return self._format_agent_label(current), next_label

        if mode == "least-used":
            tasks = getattr(self, "_tasks", {}) or {}
            counts: dict[str, int] = {}
            for task in tasks.values():
                if getattr(task, "environment_id", "") != env_id:
                    continue
                if not getattr(task, "is_active", lambda: False)():
                    continue
                inst_id = str(getattr(task, "agent_instance_id", "") or "").strip()
                if inst_id:
                    counts[inst_id] = counts.get(inst_id, 0) + 1
            ordered = sorted(
                agents,
                key=lambda a: (
                    counts.get(str(getattr(a, "agent_id", "") or "").strip(), 0),
                    agents.index(a),
                ),
            )
            now = ordered[0] if ordered else current
            nxt = ordered[1] if len(ordered) > 1 else None
            return self._format_agent_label(now), (
                self._format_agent_label(nxt) if nxt else ""
            )

        # round-robin (default)
        next_idx = (current_idx + 1) % len(agents)
        return self._format_agent_label(current), self._format_agent_label(
            agents[next_idx]
        )

    @staticmethod
    def _format_agent_label(inst: object | None) -> str:
        if inst is None:
            return ""
        agent_cli = normalize_agent(str(getattr(inst, "agent_cli", "") or "codex"))
        agent_id = str(getattr(inst, "agent_id", "") or "").strip()
        display_name = format_agent_ui_label(agent_cli)
        if agent_id and agent_id != agent_cli:
            return f"{display_name} ({agent_id})"
        return display_name

    def _compute_cross_agent_config_mounts(
        self,
        *,
        env: Environment | None,
        primary_agent_cli: str,
        primary_config_dir: str,
        settings: dict[str, object] | None = None,
    ) -> list[str]:
        """Compute additional config mounts for cross-agent allowlist.

        Returns a list of mount strings (host:container:rw) for allowlisted agents.
        Validates config dirs and enforces one-per-CLI constraint.

        Args:
            env: Environment object with cross_agent_allowlist
            primary_agent_cli: The primary agent CLI (to avoid duplicates)
            primary_config_dir: The primary agent's config dir (to avoid duplicates)
            settings: Optional settings dict; uses self._settings_data if None

        Returns:
            List of mount strings in Docker -v format (host:container:rw)
        """
        settings = settings or self._settings_data

        # Early return if cross-agents not enabled or no environment
        if not env or not getattr(env, "use_cross_agents", False):
            return []

        allowlist = list(getattr(env, "cross_agent_allowlist", []) or [])
        if not allowlist:
            return []

        # Get agent instances from environment
        agent_selection = getattr(env, "agent_selection", None)
        if not agent_selection or not getattr(agent_selection, "agents", None):
            return []

        agents = list(agent_selection.agents or [])
        if not agents:
            return []

        # Build map of agent_id -> AgentInstance
        agents_by_id = {
            str(getattr(inst, "agent_id", "") or "").strip(): inst
            for inst in agents
            if str(getattr(inst, "agent_id", "") or "").strip()
        }

        # Track which CLIs we've already mounted (including primary)
        mounted_clis: set[str] = {normalize_agent(primary_agent_cli)}
        mounted_dirs: set[str] = {os.path.expanduser(primary_config_dir)}
        mounted_container_paths: set[str] = {
            container_config_dir(normalize_agent(primary_agent_cli))
        }

        mounts: list[str] = []

        for agent_id in allowlist:
            agent_id = str(agent_id or "").strip()
            if not agent_id:
                continue

            # Look up agent instance
            inst = agents_by_id.get(agent_id)
            if inst is None:
                logger.warning(
                    f"Cross-agent allowlist references unknown agent_id: {agent_id}"
                )
                continue

            # Get agent CLI and normalize
            inst_cli = normalize_agent(str(getattr(inst, "agent_cli", "") or ""))

            # Enforce one-per-CLI constraint
            if inst_cli in mounted_clis:
                logger.debug(
                    f"Skipping allowlisted agent {agent_id} ({inst_cli}): "
                    f"already mounted config for this CLI"
                )
                continue

            # Resolve config directory
            inst_dir = os.path.expanduser(
                str(getattr(inst, "config_dir", "") or "").strip()
            )
            if not inst_dir:
                inst_dir = self._resolve_config_dir_for_agent(
                    agent_cli=inst_cli,
                    env=env,
                    settings=settings,
                )

            # Validate config directory exists
            if not self._ensure_agent_config_dir(inst_cli, inst_dir):
                # Error already shown to user
                continue

            # Check for duplicate mount (same dir as primary or already mounted)
            inst_dir_expanded = os.path.expanduser(inst_dir)
            if inst_dir_expanded in mounted_dirs:
                logger.debug(
                    f"Skipping allowlisted agent {agent_id} ({inst_cli}): "
                    f"config dir already mounted"
                )
                continue

            # Build mount string and check for duplicate container path
            container_dir = container_config_dir(inst_cli)
            if container_dir in mounted_container_paths:
                logger.debug(
                    f"Skipping allowlisted agent {agent_id} ({inst_cli}): "
                    f"container path {container_dir} already mounted"
                )
                continue

            mount_str = f"{inst_dir_expanded}:{container_dir}:rw"
            mounts.append(mount_str)

            # Track mounted CLI, dir, and container path
            mounted_clis.add(inst_cli)
            mounted_dirs.add(inst_dir_expanded)
            mounted_container_paths.add(container_dir)

            # Add additional config mounts (e.g., ~/.claude.json)
            extra_mounts = additional_config_mounts(inst_cli, inst_dir_expanded)
            for extra in extra_mounts:
                if extra and extra not in mounts:
                    mounts.append(extra)

        return mounts
