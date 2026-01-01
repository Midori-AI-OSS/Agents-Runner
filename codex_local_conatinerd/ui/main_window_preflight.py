from __future__ import annotations

import os
import shutil
import time

from datetime import datetime
from datetime import timezone
from uuid import uuid4

from PySide6.QtCore import Qt
from PySide6.QtCore import QThread

from PySide6.QtWidgets import QMessageBox

from codex_local_conatinerd.agent_cli import normalize_agent
from codex_local_conatinerd.docker_runner import DockerRunnerConfig
from codex_local_conatinerd.environments import Environment
from codex_local_conatinerd.ui.bridges import TaskRunnerBridge
from codex_local_conatinerd.ui.constants import PIXELARCH_EMERALD_IMAGE
from codex_local_conatinerd.ui.task_model import Task
from codex_local_conatinerd.ui.utils import _stain_color


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
            QMessageBox.critical(self, "Docker not found", "Could not find `docker` in PATH.")
            return

        if not os.path.isdir(host_workdir):
            QMessageBox.warning(self, "Invalid Workdir", "Host Workdir does not exist.")
            return

        if not (settings_preflight_script or "").strip() and not (environment_preflight_script or "").strip():
            QMessageBox.information(self, "Nothing to test", "No preflight scripts are enabled.")
            return

        agent_cli = normalize_agent(str(agent_cli or self._settings_data.get("use") or "codex"))
        host_codex = os.path.expanduser(str(host_codex or "").strip())
        if not host_codex:
            host_codex = self._effective_host_config_dir(agent_cli=agent_cli, env=env)
        if not self._ensure_agent_config_dir(agent_cli, host_codex):
            return

        task_id = uuid4().hex[:10]
        image = PIXELARCH_EMERALD_IMAGE

        task = Task(
            task_id=task_id,
            prompt=label,
            image=image,
            host_workdir=host_workdir,
            host_codex_dir=host_codex,
            environment_id=env.env_id,
            created_at_s=time.time(),
            status="pulling",
        )
        self._tasks[task_id] = task
        stain = env.color if env else None
        spinner = _stain_color(env.color) if env else None
        self._dashboard.upsert_task(task, stain=stain, spinner_color=spinner)
        self._schedule_save()

        config = DockerRunnerConfig(
            task_id=task_id,
            image=image,
            host_codex_dir=host_codex,
            host_workdir=host_workdir,
            agent_cli=agent_cli,
            auto_remove=True,
            pull_before_run=True,
            settings_preflight_script=settings_preflight_script,
            environment_preflight_script=environment_preflight_script,
            env_vars=dict(env.env_vars) if env else {},
            extra_mounts=list(env.extra_mounts) if env else [],
            agent_cli_args=[],
        )
        bridge = TaskRunnerBridge(task_id=task_id, config=config, mode="preflight")
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
        self._show_dashboard()
        self._schedule_save()


    def _on_settings_test_preflight(self, settings: dict) -> None:
        settings_enabled = bool(settings.get("preflight_enabled") or False)
        settings_script: str | None = None
        if settings_enabled:
            candidate = str(settings.get("preflight_script") or "")
            if candidate.strip():
                settings_script = candidate

        host_workdir_base = str(self._settings_data.get("host_workdir") or os.getcwd())
        agent_cli = normalize_agent(str(settings.get("use") or self._settings_data.get("use") or "codex"))
        host_codex_base = self._effective_host_config_dir(agent_cli=agent_cli, env=None, settings=settings)

        if settings_script is None:
            has_env_preflights = any(
                e.preflight_enabled and (e.preflight_script or "").strip() for e in self._environment_list()
            )
            if not has_env_preflights:
                if not settings_enabled:
                    return
                QMessageBox.information(self, "Nothing to test", "No preflight scripts are enabled.")
                return

        skipped: list[str] = []
        started = 0
        for env in self._environment_list():
            env_script: str | None = None
            candidate = str(env.preflight_script or "")
            if env.preflight_enabled and candidate.strip():
                env_script = candidate

            if settings_script is None and env_script is None:
                continue

            host_workdir = self._environment_effective_workdir(env, fallback=host_workdir_base)
            host_codex = env.host_codex_dir or host_codex_base
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
            if not settings_enabled:
                return
            QMessageBox.information(self, "Nothing to test", "No preflight scripts are enabled.")
            return

        if skipped:
            QMessageBox.warning(
                self,
                "Skipped environments",
                "Skipped environments with missing Workdir:\n" + "\n".join(skipped[:20]),
            )


    def _on_environment_test_preflight(self, env: object) -> None:
        if not isinstance(env, Environment):
            return

        settings_preflight_script: str | None = None
        if self._settings_data.get("preflight_enabled") and str(self._settings_data.get("preflight_script") or "").strip():
            settings_preflight_script = str(self._settings_data.get("preflight_script") or "")

        environment_preflight_script: str | None = None
        if env.preflight_enabled and (env.preflight_script or "").strip():
            environment_preflight_script = env.preflight_script

        host_workdir_base = str(self._settings_data.get("host_workdir") or os.getcwd())
        agent_cli = normalize_agent(str(self._settings_data.get("use") or "codex"))
        host_codex_base = self._effective_host_config_dir(agent_cli=agent_cli, env=None)
        host_workdir = self._environment_effective_workdir(env, fallback=host_workdir_base)
        host_codex = env.host_codex_dir or host_codex_base

        self._start_preflight_task(
            label=f"Preflight test: {env.name or env.env_id}",
            env=env,
            agent_cli=agent_cli,
            host_workdir=host_workdir,
            host_codex=host_codex,
            settings_preflight_script=settings_preflight_script,
            environment_preflight_script=environment_preflight_script,
        )
