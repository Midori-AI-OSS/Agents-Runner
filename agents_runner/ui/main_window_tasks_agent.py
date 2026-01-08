from __future__ import annotations

import logging
import os
import shlex
import shutil
import time

from uuid import uuid4

from PySide6.QtCore import Qt
from PySide6.QtCore import QThread

from PySide6.QtWidgets import QMessageBox

from agents_runner.environments import GH_MANAGEMENT_GITHUB
from agents_runner.environments import GH_MANAGEMENT_NONE
from agents_runner.environments import normalize_gh_management_mode
from agents_runner.environments import save_environment
from agents_runner.environments.cleanup import cleanup_task_workspace
from agents_runner.gh_management import is_gh_available
from agents_runner.docker_runner import DockerRunnerConfig
from agents_runner.pr_metadata import ensure_pr_metadata_file
from agents_runner.pr_metadata import pr_metadata_container_path
from agents_runner.pr_metadata import pr_metadata_host_path
from agents_runner.pr_metadata import pr_metadata_prompt_instructions
from agents_runner.prompt_sanitizer import sanitize_prompt
from agents_runner.persistence import save_task_payload
from agents_runner.persistence import serialize_task
from agents_runner.ui.bridges import TaskRunnerBridge
from agents_runner.ui.constants import PIXELARCH_AGENT_CONTEXT_SUFFIX
from agents_runner.ui.constants import PIXELARCH_EMERALD_IMAGE
from agents_runner.ui.constants import PIXELARCH_GIT_CONTEXT_SUFFIX
from agents_runner.ui.task_model import Task
from agents_runner.ui.utils import _stain_color

logger = logging.getLogger(__name__)


class _MainWindowTasksAgentMixin:
    def _clean_old_tasks(self) -> None:
        to_remove: set[str] = set()
        for task_id, task in list(self._tasks.items()):
            status = (task.status or "").lower()
            if status in {"done", "failed", "error"} and not task.is_active():
                to_remove.add(task_id)
        if not to_remove:
            return

        # Archive tasks and clean up workspaces
        data_dir = os.path.dirname(self._state_path)
        for task_id in sorted(to_remove):
            task = self._tasks.get(task_id)
            if task is None:
                continue
            status = (task.status or "").lower()
            save_task_payload(self._state_path, serialize_task(task), archived=True)

            # Clean up task workspace (if using GitHub management)
            gh_mode = normalize_gh_management_mode(task.gh_management_mode)
            if gh_mode == GH_MANAGEMENT_GITHUB and task.environment_id:
                # Keep failed task repos for debugging (unless status is "done")
                keep_on_error = status in {"failed", "error"}
                if not keep_on_error:
                    cleanup_task_workspace(
                        env_id=task.environment_id,
                        task_id=task_id,
                        data_dir=data_dir,
                        on_log=None,  # Silent cleanup
                    )

        self._dashboard.remove_tasks(to_remove)
        for task_id in to_remove:
            self._tasks.pop(task_id, None)
            self._threads.pop(task_id, None)
            self._bridges.pop(task_id, None)
            self._run_started_s.pop(task_id, None)
            self._dashboard_log_refresh_s.pop(task_id, None)
        self._schedule_save()

    def _start_task_from_ui(
        self,
        prompt: str,
        host_codex: str,
        env_id: str,
        base_branch: str,
    ) -> None:
        if shutil.which("docker") is None:
            QMessageBox.critical(
                self, "Docker not found", "Could not find `docker` in PATH."
            )
            return
        prompt = sanitize_prompt((prompt or "").strip())

        task_id = uuid4().hex[:10]
        env_id = str(env_id or "").strip() or self._active_environment_id()
        if env_id not in self._environments:
            QMessageBox.warning(
                self, "Unknown environment", "Pick an environment first."
            )
            return
        self._settings_data["active_environment_id"] = env_id
        env = self._environments.get(env_id)

        # Get effective agent and config dir (environment agent_selection overrides settings)
        agent_instance_id = ""
        if env and env.agent_selection and getattr(env.agent_selection, "agents", None):
            agent_cli, auto_config_dir, agent_instance_id = (
                self._select_agent_instance_for_env(
                    env=env,
                    settings=self._settings_data,
                    advance_round_robin=True,
                )
            )
        else:
            agent_cli, auto_config_dir = self._effective_agent_and_config(
                env=env, advance_round_robin=True
            )

        gh_mode = (
            normalize_gh_management_mode(
                str(env.gh_management_mode or GH_MANAGEMENT_NONE)
            )
            if env
            else GH_MANAGEMENT_NONE
        )
        effective_workdir, ready, message = self._new_task_workspace(
            env, task_id=task_id
        )
        if not ready:
            QMessageBox.warning(self, "Workspace not configured", message)
            return
        if gh_mode == GH_MANAGEMENT_GITHUB:
            try:
                os.makedirs(effective_workdir, exist_ok=True)
            except Exception as exc:
                logger.error(f"Failed to create directory {effective_workdir}: {exc}")
                QMessageBox.warning(
                    self,
                    "Directory Creation Failed",
                    f"Could not create workspace directory: {exc}",
                )
                return
        elif not os.path.isdir(effective_workdir):
            QMessageBox.warning(self, "Invalid Workdir", "Host Workdir does not exist.")
            return

        self._settings_data["host_workdir"] = effective_workdir
        host_codex = os.path.expanduser(str(host_codex or "").strip())
        if not host_codex:
            host_codex = auto_config_dir
        if not self._ensure_agent_config_dir(agent_cli, host_codex):
            return
        self._settings_data[self._host_config_dir_key(agent_cli)] = host_codex

        image = PIXELARCH_EMERALD_IMAGE

        agent_cli_args: list[str] = []
        if env and env.agent_cli_args.strip():
            try:
                agent_cli_args = shlex.split(env.agent_cli_args)
            except ValueError as exc:
                QMessageBox.warning(self, "Invalid agent CLI flags", str(exc))
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
        if env and env.preflight_enabled and (env.preflight_script or "").strip():
            environment_preflight_script = env.preflight_script

        force_headless_desktop = bool(
            self._settings_data.get("headless_desktop_enabled") or False
        )
        env_headless_desktop = (
            bool(getattr(env, "headless_desktop_enabled", False)) if env else False
        )
        headless_desktop_enabled = bool(force_headless_desktop or env_headless_desktop)

        task = Task(
            task_id=task_id,
            prompt=prompt,
            image=image,
            host_workdir=effective_workdir,
            host_codex_dir=host_codex,
            environment_id=env_id,
            created_at_s=time.time(),
            status="queued",
            gh_management_mode=gh_mode,
            agent_cli=agent_cli,
            agent_instance_id=agent_instance_id,
            agent_cli_args=" ".join(agent_cli_args),
            headless_desktop_enabled=headless_desktop_enabled,
        )
        self._tasks[task_id] = task
        stain = env.color if env else None
        spinner = _stain_color(env.color) if env else None
        self._dashboard.upsert_task(task, stain=stain, spinner_color=spinner)
        self._schedule_save()

        use_host_gh = bool(getattr(env, "gh_use_host_cli", True)) if env else True
        use_host_gh = bool(use_host_gh and is_gh_available())
        task.gh_use_host_cli = use_host_gh

        desired_base = str(base_branch or "").strip()

        # Save the selected branch for locked environments
        if (
            env
            and env.gh_management_locked
            and desired_base
            and gh_mode == GH_MANAGEMENT_GITHUB
        ):
            env.gh_last_base_branch = desired_base
            save_environment(env)
            # Update in-memory copy to persist across tab changes and reloads
            self._environments[env.env_id] = env

        runner_prompt = prompt
        if bool(self._settings_data.get("append_pixelarch_context") or False):
            runner_prompt = f"{runner_prompt.rstrip()}{PIXELARCH_AGENT_CONTEXT_SUFFIX}"

        # Inject git context when GitHub management is enabled
        if gh_mode == GH_MANAGEMENT_GITHUB:
            runner_prompt = f"{runner_prompt.rstrip()}{PIXELARCH_GIT_CONTEXT_SUFFIX}"

        enabled_env_prompts: list[str] = []
        if env and bool(getattr(env, "prompts_unlocked", False)):
            for p in getattr(env, "prompts", None) or []:
                text = str(getattr(p, "text", "") or "").strip()
                if not text or not bool(getattr(p, "enabled", False)):
                    continue
                enabled_env_prompts.append(sanitize_prompt(text))

        if enabled_env_prompts:
            runner_prompt = f"{runner_prompt.rstrip()}\n\n" + "\n\n".join(
                enabled_env_prompts
            )
            self._on_task_log(
                task_id,
                f"[env] appended {len(enabled_env_prompts)} environment prompt(s) (non-interactive)",
            )
        env_vars_for_task = dict(env.env_vars) if env else {}
        extra_mounts_for_task = list(env.extra_mounts) if env else []

        # PR metadata prep (only if gh mode is enabled)
        # Note: We prepare the PR metadata file before the task starts, even though
        # gh_repo_root and gh_branch won't be available until after the git clone
        # completes in the worker. This is fine because the file is created with just
        # the task_id, and the actual branch/repo info is captured later when the
        # worker completes (see _on_bridge_done in main_window_task_events.py).
        # If the git clone fails, the orphaned metadata file is harmless and will be
        # cleaned up with other temp files.
        if (
            env
            and gh_mode == GH_MANAGEMENT_GITHUB
            and bool(getattr(env, "gh_pr_metadata_enabled", False))
        ):
            host_path = pr_metadata_host_path(
                os.path.dirname(self._state_path), task_id
            )
            container_path = pr_metadata_container_path(task_id)
            try:
                ensure_pr_metadata_file(host_path, task_id=task_id)
            except Exception as exc:
                self._on_task_log(
                    task_id, f"[gh] failed to prepare PR metadata file: {exc}"
                )
            else:
                task.gh_pr_metadata_path = host_path
                extra_mounts_for_task.append(f"{host_path}:{container_path}:rw")
                env_vars_for_task.setdefault("CODEX_PR_METADATA_PATH", container_path)
                runner_prompt = (
                    f"{runner_prompt}{pr_metadata_prompt_instructions(container_path)}"
                )
                self._on_task_log(
                    task_id, f"[gh] PR metadata enabled; mounted -> {container_path}"
                )

        # Build config with GitHub repo info if needed
        gh_repo: str | None = None
        if gh_mode == GH_MANAGEMENT_GITHUB and env:
            gh_repo = str(env.gh_management_target or "").strip() or None

        config = DockerRunnerConfig(
            task_id=task_id,
            image=image,
            host_codex_dir=host_codex,
            host_workdir=effective_workdir,
            agent_cli=agent_cli,
            environment_id=env_id,
            auto_remove=True,
            pull_before_run=True,
            settings_preflight_script=settings_preflight_script,
            environment_preflight_script=environment_preflight_script,
            headless_desktop_enabled=headless_desktop_enabled,
            env_vars=env_vars_for_task,
            extra_mounts=extra_mounts_for_task,
            agent_cli_args=agent_cli_args,
            gh_repo=gh_repo,
            gh_prefer_gh_cli=use_host_gh,
            gh_recreate_if_needed=True,
            gh_base_branch=desired_base or None,
        )
        task._runner_config = config
        task._runner_prompt = runner_prompt

        if self._can_start_new_agent_for_env(env_id):
            self._actually_start_task(task)
        else:
            self._on_task_log(task_id, "[queue] Waiting for available slot...")
            self._dashboard.upsert_task(task, stain=stain, spinner_color=spinner)
            self._schedule_save()

        self._show_dashboard()
        self._new_task.reset_for_new_run()

    def _actually_start_task(self, task: Task) -> None:
        config = getattr(task, "_runner_config", None)
        prompt = getattr(task, "_runner_prompt", None)
        if config is None or prompt is None:
            return

        task.status = "pulling"
        env = self._environments.get(task.environment_id)
        stain = env.color if env else None
        spinner = _stain_color(env.color) if env else None
        self._dashboard.upsert_task(task, stain=stain, spinner_color=spinner)

        bridge = TaskRunnerBridge(task_id=task.task_id, config=config, prompt=prompt)
        thread = QThread(self)
        bridge.moveToThread(thread)
        thread.started.connect(bridge.run)

        bridge.state.connect(self._on_bridge_state, Qt.QueuedConnection)
        bridge.log.connect(self._on_bridge_log, Qt.QueuedConnection)
        bridge.done.connect(self._on_bridge_done, Qt.QueuedConnection)

        bridge.done.connect(thread.quit, Qt.QueuedConnection)
        bridge.done.connect(bridge.deleteLater, Qt.QueuedConnection)
        thread.finished.connect(thread.deleteLater)

        self._bridges[task.task_id] = bridge
        self._threads[task.task_id] = thread
        self._run_started_s[task.task_id] = time.time()

        thread.start()
        self._schedule_save()
