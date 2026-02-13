from __future__ import annotations

import os
import shutil
import time

from uuid import uuid4

from PySide6.QtCore import Qt
from PySide6.QtCore import QThread

from PySide6.QtWidgets import QMessageBox

from agents_runner.agent_cli import normalize_agent
from agents_runner.docker_runner import DockerRunnerConfig
from agents_runner.environments import Environment
from agents_runner.environments import WORKSPACE_CLONED
from agents_runner.environments import WORKSPACE_NONE
from agents_runner.gh_management import is_gh_available
from agents_runner.ui.bridges import TaskRunnerBridge
from agents_runner.ui.constants import PIXELARCH_EMERALD_IMAGE
from agents_runner.ui.task_model import Task
from agents_runner.ui.utils import _stain_color


class _MainWindowPreflightMixin:
    def _start_preflight_task(
        self,
        *,
        label: str,
        env: Environment,
        agent_cli: str | None,
        host_workdir: str,
        host_codex: str,
        settings_preflight_script: str | None,
        environment_preflight_script: str | None,
    ) -> None:
        if shutil.which("docker") is None:
            QMessageBox.critical(
                self, "Docker not found", "Could not find `docker` in PATH."
            )
            return

        if not os.path.isdir(host_workdir):
            QMessageBox.warning(self, "Invalid Workdir", "Host Workdir does not exist.")
            return

        smoke_agent_cli = "sh"
        agent_cli = normalize_agent(
            str(agent_cli or self._settings_data.get("use") or "codex")
        )
        host_codex = os.path.expanduser(str(host_codex or "").strip())
        if not host_codex:
            host_codex = self._effective_host_config_dir(agent_cli=agent_cli, env=env)
        if not self._ensure_agent_config_dir(smoke_agent_cli, host_codex):
            return

        task_id = uuid4().hex[:10]
        image = PIXELARCH_EMERALD_IMAGE

        # Determine git management settings based on workspace_type
        workspace_type = env.workspace_type if env else WORKSPACE_NONE
        gh_repo: str = ""
        gh_base_branch: str | None = None
        gh_prefer_gh_cli = bool(getattr(env, "gh_use_host_cli", True)) if env else True
        # Cloned workspaces can be recreated; mounted/none cannot
        gh_recreate_if_needed = workspace_type == WORKSPACE_CLONED

        if workspace_type == WORKSPACE_CLONED and env:
            gh_repo = str(env.workspace_target or "").strip()
            # Use the first non-empty agent_cli_arg as base branch, or empty
            args_list = [
                a.strip() for a in (env.agent_cli_args or "").split() if a.strip()
            ]
            gh_base_branch = args_list[0] if args_list else None

        # Check gh CLI availability if needed
        if gh_repo and gh_prefer_gh_cli:
            gh_prefer_gh_cli = gh_prefer_gh_cli and is_gh_available()

        task = Task(
            task_id=task_id,
            prompt=label,
            image=image,
            host_workdir=host_workdir,
            host_config_dir=host_codex,
            environment_id=env.env_id,
            created_at_s=time.time(),
            status="pulling",
        )
        self._tasks[task_id] = task
        stain = env.color if env else None
        spinner = _stain_color(env.color) if env else None
        self._dashboard.upsert_task(task, stain=stain, spinner_color=spinner)
        self._schedule_save()

        if env:
            task.workspace_type = env.workspace_type

        force_headless_desktop = bool(
            self._settings_data.get("headless_desktop_enabled") or False
        )
        env_headless_desktop = bool(getattr(env, "headless_desktop_enabled", False))
        headless_desktop_enabled = bool(force_headless_desktop or env_headless_desktop)
        desktop_cache_enabled = bool(getattr(env, "cache_desktop_build", False))
        desktop_cache_enabled = desktop_cache_enabled and headless_desktop_enabled
        smoke_command = f'echo "preflight smoke: {env.name or env.env_id}"; sleep 10'

        config = DockerRunnerConfig(
            task_id=task_id,
            image=image,
            host_config_dir=host_codex,
            host_workdir=host_workdir,
            agent_cli=smoke_agent_cli,
            environment_id=env.env_id if env else "",
            auto_remove=True,
            pull_before_run=True,
            settings_preflight_script=settings_preflight_script,
            environment_preflight_script=environment_preflight_script,
            headless_desktop_enabled=headless_desktop_enabled,
            desktop_cache_enabled=desktop_cache_enabled,
            container_caching_enabled=bool(
                getattr(env, "container_caching_enabled", False)
            ),
            cache_system_preflight_enabled=bool(
                getattr(env, "cache_system_preflight_enabled", False)
            ),
            cache_settings_preflight_enabled=bool(
                getattr(env, "cache_settings_preflight_enabled", False)
            ),
            cache_environment_preflight_enabled=bool(
                getattr(env, "cache_environment_preflight_enabled", False)
            ),
            env_vars=dict(env.env_vars) if env else {},
            extra_mounts=self._get_extra_mounts_with_cache(env),
            agent_cli_args=["-c", smoke_command],
            gh_repo=gh_repo or None,
            gh_prefer_gh_cli=gh_prefer_gh_cli,
            gh_recreate_if_needed=gh_recreate_if_needed,
            gh_base_branch=gh_base_branch,
        )

        # Clean up any existing bridge/thread for this task to prevent duplicate log emissions
        old_bridge = self._bridges.pop(task_id, None)
        old_thread = self._threads.pop(task_id, None)
        if old_bridge is not None:
            try:
                # Disconnect all signal connections to prevent duplicate log emissions
                old_bridge.log.disconnect()
                old_bridge.state.disconnect()
                old_bridge.done.disconnect()
                # Preflight bridges don't have these signals, but disconnect them for consistency
                if hasattr(old_bridge, "retry_attempt"):
                    old_bridge.retry_attempt.disconnect()
                if hasattr(old_bridge, "agent_switched"):
                    old_bridge.agent_switched.disconnect()
            except Exception:
                pass
            try:
                # Request the bridge to stop
                old_bridge.request_stop()
            except Exception:
                pass
            try:
                # Schedule deletion on next event loop iteration
                old_bridge.deleteLater()
            except Exception:
                pass
        if old_thread is not None:
            try:
                # Request thread to quit and wait for it to finish
                old_thread.quit()
                old_thread.wait(100)  # Wait up to 100ms for graceful shutdown
            except Exception:
                pass

        bridge = TaskRunnerBridge(
            task_id=task_id,
            config=config,
            prompt="",
            mode="codex",
            use_supervisor=False,
        )
        thread = QThread(self)
        bridge.moveToThread(thread)
        thread.started.connect(bridge.run)

        bridge.state.connect(self._on_bridge_state, Qt.QueuedConnection)
        bridge.log.connect(self._on_bridge_log, Qt.QueuedConnection)
        bridge.done.connect(self._on_bridge_done, Qt.QueuedConnection)

        bridge.done.connect(thread.quit, Qt.QueuedConnection)
        bridge.done.connect(bridge.deleteLater, Qt.QueuedConnection)
        thread.finished.connect(thread.deleteLater)

        self._bridges[task_id] = bridge
        self._threads[task_id] = thread
        self._run_started_s[task_id] = time.time()

        thread.start()
        self._maybe_auto_navigate_on_task_start(interactive=False)
        self._schedule_save()

    def _on_settings_test_preflight(self, settings: dict) -> None:
        settings_enabled = bool(settings.get("preflight_enabled") or False)
        settings_script: str | None = None
        if settings_enabled:
            candidate = str(settings.get("preflight_script") or "")
            if candidate.strip():
                settings_script = candidate

        host_workdir_base = str(self._settings_data.get("host_workdir") or os.getcwd())

        skipped: list[str] = []
        started = 0
        for env in self._environment_list():
            env_script: str | None = None
            candidate = str(env.preflight_script or "")
            if env.preflight_enabled and candidate.strip():
                env_script = candidate

            # Get effective agent and config for each environment
            agent_cli, host_codex = self._effective_agent_and_config(
                env=env, settings=settings
            )
            host_workdir = self._environment_effective_workdir(
                env, fallback=host_workdir_base
            )
            if not os.path.isdir(host_workdir):
                skipped.append(f"{env.name or env.env_id} ({host_workdir})")
                continue
            self._start_preflight_task(
                label=f"Preflight test (all): {env.name or env.env_id}",
                env=env,
                agent_cli=agent_cli,
                host_workdir=host_workdir,
                host_codex=host_codex,
                settings_preflight_script=settings_script,
                environment_preflight_script=env_script,
            )
            started += 1

        if started == 0 and not skipped:
            return

        if skipped:
            QMessageBox.warning(
                self,
                "Skipped environments",
                "Skipped environments with missing Workdir:\n"
                + "\n".join(skipped[:20]),
            )

    def _on_environment_test_preflight(self, env: object) -> None:
        if not isinstance(env, Environment):
            return

        settings_preflight_script: str | None = None
        if (
            self._settings_data.get("preflight_enabled")
            and str(self._settings_data.get("preflight_script") or "").strip()
        ):
            settings_preflight_script = str(
                self._settings_data.get("preflight_script") or ""
            )

        environment_preflight_script: str | None = None
        if env.preflight_enabled and (env.preflight_script or "").strip():
            environment_preflight_script = env.preflight_script

        host_workdir_base = str(self._settings_data.get("host_workdir") or os.getcwd())
        # Get effective agent and config for this environment
        agent_cli, host_codex = self._effective_agent_and_config(env=env)
        host_workdir = self._environment_effective_workdir(
            env, fallback=host_workdir_base
        )

        self._start_preflight_task(
            label=f"Preflight test: {env.name or env.env_id}",
            env=env,
            agent_cli=agent_cli,
            host_workdir=host_workdir,
            host_codex=host_codex,
            settings_preflight_script=settings_preflight_script,
            environment_preflight_script=environment_preflight_script,
        )

    def _get_extra_mounts_with_cache(self, env: Environment | None) -> list[str]:
        """Get extra mounts list with optional host cache mount if enabled."""
        extra_mounts = list(env.extra_mounts) if env else []

        # Add host cache mount if enabled in settings
        if self._settings_data.get("mount_host_cache", False):
            host_cache = os.path.expanduser("~/.cache")
            container_cache = "/home/midori-ai/.cache"
            extra_mounts.append(f"{host_cache}:{container_cache}:rw")

        return extra_mounts
