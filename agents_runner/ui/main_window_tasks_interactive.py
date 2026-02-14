"""Interactive task launching orchestration for MainWindow.

This module handles the high-level orchestration of interactive task launching,
including validation, agent selection, workspace setup, and delegation to
specialized modules for command building and Docker launching.
"""

from __future__ import annotations

import os
import shlex
import shutil
import threading
import time
from datetime import datetime
from datetime import timezone
from uuid import uuid4

from PySide6.QtCore import Qt
from PySide6.QtCore import QThread
from PySide6.QtWidgets import QMessageBox

from agents_runner.agent_cli import additional_config_mounts
from agents_runner.agent_cli import container_config_dir
from agents_runner.environments import WORKSPACE_CLONED
from agents_runner.environments import save_environment
from agents_runner.gh_management import is_gh_available
from agents_runner.log_format import format_log
from agents_runner.prompt_sanitizer import sanitize_prompt
from agents_runner.terminal_apps import detect_terminal_options
from agents_runner.ui.constants import PIXELARCH_AGENT_CONTEXT_SUFFIX
from agents_runner.ui.constants import PIXELARCH_EMERALD_IMAGE
from agents_runner.ui.constants import PIXELARCH_GIT_CONTEXT_SUFFIX
from agents_runner.ui.interactive_prep_diagnostics import (
    log_interactive_prep_diag,
)
from agents_runner.ui.interactive_prep_bridge import InteractivePrepBridge
from agents_runner.ui.main_window_tasks_interactive_docker import (
    launch_docker_terminal_task,
)
from agents_runner.ui.interactive_prep_worker import InteractivePrepWorker
from agents_runner.ui.task_model import Task
from agents_runner.ui.utils import _stain_color
from midori_ai_logger import MidoriAiLogger

logger = MidoriAiLogger(channel=None, name=__name__)


class _MainWindowTasksInteractiveMixin:
    def _start_interactive_task_from_ui(
        self,
        prompt: str,
        command: str,
        host_codex: str,
        env_id: str,
        terminal_id: str,
        base_branch: str,
        extra_preflight_script: str,
    ) -> None:
        if shutil.which("docker") is None:
            QMessageBox.critical(
                self, "Docker not found", "Could not find `docker` in PATH."
            )
            return

        prompt = sanitize_prompt((prompt or "").strip())
        has_typed_prompt = bool(str(prompt or "").strip())
        host_codex = os.path.expanduser((host_codex or "").strip())

        options = {opt.terminal_id: opt for opt in detect_terminal_options()}
        opt = options.get(str(terminal_id or "").strip())
        if opt is None:
            QMessageBox.warning(
                self,
                "Terminal not available",
                "The selected terminal could not be found.",
            )
            return

        env_id = str(env_id or "").strip() or self._active_environment_id()
        if env_id not in self._environments:
            QMessageBox.warning(
                self, "Unknown environment", "Pick an environment first."
            )
            return
        env = self._environments.get(env_id)

        task_id = uuid4().hex[:10]
        task_token = f"interactive-{task_id}"

        workspace_type = env.workspace_type if env else "none"
        host_workdir, ready, message = self._new_task_workspace(env, task_id=task_id)
        if not ready:
            QMessageBox.warning(self, "Workspace not configured", message)
            return

        if workspace_type != WORKSPACE_CLONED and not os.path.isdir(host_workdir):
            QMessageBox.warning(self, "Invalid Workdir", "Host Workdir does not exist.")
            return

        if env and os.path.isdir(host_workdir):
            try:
                from agents_runner.midoriai_template import (
                    scan_midoriai_agents_template,
                )

                # Only update template detection if not already set
                # For cloned workspaces, we scan once and persist the result
                if env.midoriai_template_likelihood == 0.0:
                    detection = scan_midoriai_agents_template(host_workdir)
                    env.midoriai_template_likelihood = (
                        detection.midoriai_template_likelihood
                    )
                    env.midoriai_template_detected = (
                        detection.midoriai_template_detected
                    )
                    env.midoriai_template_detected_path = (
                        detection.midoriai_template_detected_path
                    )
                    save_environment(env)
                    self._environments[env.env_id] = env
            except Exception:
                pass

        desired_base = str(base_branch or "").strip()

        # Save the selected branch for cloned environments
        if env and env.workspace_type == WORKSPACE_CLONED and desired_base:
            env.gh_last_base_branch = desired_base
            save_environment(env)
            # Update in-memory copy to persist across tab changes and reloads
            self._environments[env.env_id] = env

        if (
            env
            and env.agent_selection
            and str(getattr(env.agent_selection, "selection_mode", "") or "")
            .strip()
            .lower()
            == "pinned"
        ):
            pinned_id = str(
                getattr(env.agent_selection, "pinned_agent_id", "") or ""
            ).strip()
            pinned_lower = pinned_id.lower()
            pinned_inst = next(
                (
                    inst
                    for inst in list(getattr(env.agent_selection, "agents", []) or [])
                    if str(getattr(inst, "agent_id", "") or "").strip() == pinned_id
                ),
                None,
            ) or next(
                (
                    inst
                    for inst in list(getattr(env.agent_selection, "agents", []) or [])
                    if str(getattr(inst, "agent_id", "") or "").strip().lower()
                    == pinned_lower
                ),
                None,
            )
            if pinned_inst is None:
                QMessageBox.warning(
                    self,
                    "Pinned agent missing",
                    "This environment is set to Pinned mode, but the pinned agent ID is missing or invalid.",
                )
                return

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
        if not host_codex:
            host_codex = auto_config_dir
        if not self._ensure_agent_config_dir(agent_cli, host_codex):
            return

        agent_cli_args: list[str] = []
        if env and env.agent_cli_args.strip():
            try:
                agent_cli_args = shlex.split(env.agent_cli_args)
            except ValueError as exc:
                QMessageBox.warning(self, "Invalid agent CLI flags", str(exc))
                return

        # Build command with agent-specific handling
        raw_command = str(command or "").strip()
        if not raw_command:
            raw_command = self._default_interactive_command(agent_cli)
        command = raw_command
        extra_preflight_script = str(extra_preflight_script or "")
        is_help_launch = self._is_agent_help_interactive_launch(
            prompt=prompt, command=command
        )
        if extra_preflight_script.strip() and "clone_repo" in extra_preflight_script:
            is_help_launch = True
        if is_help_launch:
            prompt = "\n".join(
                [
                    f"You are running: `{agent_cli}` right now",
                    "",
                    str(prompt or "").strip(),
                ]
            ).strip()

        apply_full_prompting = bool(has_typed_prompt and not is_help_launch)
        prompt_for_agent = str(prompt or "")
        if apply_full_prompting:
            prompt_for_agent = self._build_interactive_base_prompt(
                prompt=prompt_for_agent,
                workspace_type=workspace_type,
                env=env,
                task_id=task_id,
            )
        gh_use_host_cli = bool(getattr(env, "gh_use_host_cli", True)) if env else True
        gh_use_host_cli = bool(gh_use_host_cli and is_gh_available())
        gh_repo = (
            str(env.workspace_target or "").strip()
            if workspace_type == WORKSPACE_CLONED and env
            else ""
        )

        image = PIXELARCH_EMERALD_IMAGE

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

        desktop_enabled = bool(
            "websockify" in extra_preflight_script
            or "noVNC" in extra_preflight_script
            or "[desktop]" in extra_preflight_script
        )

        container_name = f"agents-runner-tui-it-{task_id}"
        container_agent_dir = container_config_dir(agent_cli)
        config_extra_mounts = additional_config_mounts(agent_cli, host_codex)

        # Add cross-agent config mounts if enabled
        cross_agent_mounts = self._compute_cross_agent_config_mounts(
            env=env,
            primary_agent_cli=agent_cli,
            primary_config_dir=host_codex,
            settings=self._settings_data,
        )
        config_extra_mounts.extend(cross_agent_mounts)

        container_workdir = "/home/midori-ai/workspace"

        task = Task(
            task_id=task_id,
            prompt=prompt,
            image=image,
            host_workdir=host_workdir,
            host_config_dir=host_codex,
            environment_id=env_id,
            created_at_s=time.time(),
            status="starting",
            container_id=container_name,
            gh_use_host_cli=gh_use_host_cli,
            agent_cli=agent_cli,
            agent_instance_id=agent_instance_id,
            agent_cli_args=" ".join(agent_cli_args),
        )
        self._tasks[task_id] = task
        stain = env.color if env else None
        spinner = _stain_color(env.color) if env else None
        self._dashboard.upsert_task(task, stain=stain, spinner_color=spinner)
        self._schedule_save()

        if env:
            task.workspace_type = env.workspace_type

        prep_id = uuid4().hex[:8]
        self._maybe_auto_navigate_on_task_start(interactive=True)
        self._new_task.reset_for_new_run()

        prep_worker = InteractivePrepWorker(
            task_id=task_id,
            env_id=env_id,
            workspace_type=workspace_type,
            gh_repo=gh_repo,
            host_workdir=host_workdir,
            desired_base=desired_base,
            gh_use_host_cli=gh_use_host_cli,
            gh_context_enabled=bool(env and env.gh_context_enabled),
            data_dir=os.path.dirname(self._state_path),
            image=image,
            command=command,
            agent_cli=agent_cli,
            agent_cli_args=agent_cli_args,
            prompt_for_agent=prompt_for_agent,
            is_help_launch=is_help_launch,
            apply_full_prompting=apply_full_prompting,
            desktop_enabled=desktop_enabled,
            settings_preflight_script=settings_preflight_script,
            extra_preflight_script=extra_preflight_script,
            container_caching_enabled=bool(
                env and getattr(env, "container_caching_enabled", False)
            ),
            cache_system_preflight_enabled=bool(
                env and getattr(env, "cache_system_preflight_enabled", False)
            ),
            cache_settings_preflight_enabled=bool(
                env and getattr(env, "cache_settings_preflight_enabled", False)
            ),
            cache_desktop_build=bool(
                env and getattr(env, "cache_desktop_build", False)
            ),
            prep_id=prep_id,
        )
        prep_thread = QThread(self)
        prep_worker.moveToThread(prep_thread)
        prep_thread.started.connect(prep_worker.run)
        self._interactive_prep_context[task_id] = {
            "env": env,
            "env_id": env_id,
            "task_token": task_token,
            "terminal_opt": opt,
            "prompt": prompt,
            "command": command,
            "agent_cli": agent_cli,
            "host_codex": host_codex,
            "host_workdir": host_workdir,
            "config_extra_mounts": list(config_extra_mounts),
            "image": image,
            "container_name": container_name,
            "container_agent_dir": container_agent_dir,
            "container_workdir": container_workdir,
            "settings_preflight_script": settings_preflight_script,
            "environment_preflight_script": environment_preflight_script,
            "extra_preflight_script": extra_preflight_script,
            "stain": stain,
            "spinner": spinner,
            "desired_base": desired_base,
            "prep_id": prep_id,
        }
        prep_bridge = InteractivePrepBridge(
            on_stage=self._on_interactive_prep_stage,
            on_log=self._on_interactive_prep_log,
            on_succeeded=self._on_interactive_prep_succeeded,
            on_failed=self._on_interactive_prep_failed,
            parent=self,
        )

        self._interactive_prep_workers[task_id] = prep_worker
        self._interactive_prep_threads[task_id] = prep_thread
        self._interactive_prep_bridges[task_id] = prep_bridge

        prep_worker.stage.connect(prep_bridge.on_stage, Qt.QueuedConnection)
        prep_worker.log.connect(prep_bridge.on_log, Qt.QueuedConnection)
        prep_worker.succeeded.connect(prep_bridge.on_succeeded, Qt.QueuedConnection)
        prep_worker.failed.connect(prep_bridge.on_failed, Qt.QueuedConnection)
        prep_worker.succeeded.connect(prep_thread.quit, Qt.QueuedConnection)
        prep_worker.failed.connect(prep_thread.quit, Qt.QueuedConnection)
        prep_worker.succeeded.connect(prep_worker.deleteLater, Qt.QueuedConnection)
        prep_worker.failed.connect(prep_worker.deleteLater, Qt.QueuedConnection)
        prep_thread.finished.connect(prep_thread.deleteLater)
        prep_thread.finished.connect(prep_bridge.deleteLater, Qt.QueuedConnection)

        prep_thread.start()

    def _build_interactive_base_prompt(
        self,
        *,
        prompt: str,
        workspace_type: str,
        env: object | None,
        task_id: str,
    ) -> str:
        runner_prompt = str(prompt or "")

        if bool(self._settings_data.get("append_pixelarch_context") or False):
            runner_prompt = f"{runner_prompt.rstrip()}{PIXELARCH_AGENT_CONTEXT_SUFFIX}"

        if workspace_type == WORKSPACE_CLONED:
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
                format_log(
                    "env",
                    "prompts",
                    "INFO",
                    f"appended {len(enabled_env_prompts)} environment prompt(s) (interactive)",
                ),
            )

        return runner_prompt

    def _interactive_prep_id(self, task_id: str) -> str:
        task_id = str(task_id or "").strip()
        context = self._interactive_prep_context.get(task_id)
        if isinstance(context, dict):
            prep_id = str(context.get("prep_id") or "").strip()
            if prep_id:
                return prep_id
        return "unknown"

    def _interactive_prep_diag_log(
        self, task_id: str, level: str, message: str
    ) -> None:
        task_id = str(task_id or "").strip()
        if not task_id:
            return
        log_interactive_prep_diag(
            main_window=self,
            task_id=task_id,
            prep_id=self._interactive_prep_id(task_id),
            level=level,
            message=message,
        )

    def _refresh_interactive_prep_task_card(self, task: Task) -> None:
        env_for_task = self._environments.get(task.environment_id)
        task_stain = env_for_task.color if env_for_task else None
        task_spinner = _stain_color(env_for_task.color) if env_for_task else None
        self._dashboard.upsert_task(task, stain=task_stain, spinner_color=task_spinner)
        self._details.update_task(task)
        self._schedule_save()

    def _clear_interactive_prep_refs(self, task_id: str) -> None:
        task_id = str(task_id or "").strip()
        if not task_id:
            return
        self._interactive_prep_context.pop(task_id, None)
        bridge = self._interactive_prep_bridges.pop(task_id, None)
        if bridge is not None:
            try:
                bridge.deleteLater()
            except Exception:
                pass
        self._interactive_prep_workers.pop(task_id, None)
        self._interactive_prep_threads.pop(task_id, None)

    def _on_interactive_prep_stage(self, task_id: str, status: str, _: str) -> None:
        task_id = str(task_id or "").strip()
        if not task_id:
            return
        status_text = str(status or "").strip().lower()
        task = self._tasks.get(task_id)
        if task is None:
            self._interactive_prep_diag_log(
                task_id, "WARN", "bridge stage callback ignored: task missing"
            )
            return
        if status_text:
            task.status = status_text
            task.error = None
        self._refresh_interactive_prep_task_card(task)

    def _on_interactive_prep_log(self, task_id: str, line: str) -> None:
        task_id = str(task_id or "").strip()
        if not task_id:
            return
        self._on_task_log(task_id, str(line or ""))

    def _on_interactive_prep_failed(self, task_id: str, error_message: str) -> None:
        task_id = str(task_id or "").strip()
        if not task_id:
            return
        task = self._tasks.get(task_id)
        if task is None:
            self._interactive_prep_diag_log(
                task_id, "WARN", "bridge failed callback ignored: task missing"
            )
            self._clear_interactive_prep_refs(task_id)
            return
        task.status = "failed"
        task.error = str(error_message or "").strip() or "Interactive prep failed"
        task.exit_code = 1
        task.finished_at = datetime.now(tz=timezone.utc)
        task.finalization_state = "done"
        self._on_task_log(
            task.task_id,
            format_log("ui", "prep", "ERROR", task.error),
        )
        self._refresh_interactive_prep_task_card(task)
        self._clear_interactive_prep_refs(task_id)

    def _on_interactive_prep_succeeded(self, task_id: str, payload: dict) -> None:
        task_id = str(task_id or "").strip()
        if not task_id:
            return
        task = self._tasks.get(task_id)
        if task is None:
            self._interactive_prep_diag_log(
                task_id, "WARN", "bridge success callback ignored: task missing"
            )
            self._clear_interactive_prep_refs(task_id)
            return

        cmd_parts = payload.get("cmd_parts")
        if not isinstance(cmd_parts, list) or not cmd_parts:
            self._on_interactive_prep_failed(
                task_id, "Interactive prep returned no command."
            )
            return

        task.gh_repo_root = str(payload.get("gh_repo_root") or "").strip()
        task.gh_base_branch = str(payload.get("gh_base_branch") or "").strip()
        task.gh_branch = str(payload.get("gh_branch") or "").strip()
        task.gh_pr_metadata_path = str(payload.get("gh_pr_metadata_path") or "").strip()
        task.error = None

        context = self._interactive_prep_context.get(task_id)
        if not isinstance(context, dict):
            self._on_interactive_prep_failed(
                task_id, "Interactive prep context is unavailable."
            )
            return
        if not task.gh_base_branch:
            task.gh_base_branch = str(context.get("desired_base") or "").strip()
        self._refresh_interactive_prep_task_card(task)

        launch_mounts = list(context.get("config_extra_mounts") or [])
        pr_metadata_mount = str(payload.get("pr_metadata_mount") or "").strip()
        if pr_metadata_mount:
            launch_mounts.append(pr_metadata_mount)

        cache_override_keys = {
            "runtime_image",
            "system_preflight_cached",
            "desktop_preflight_cached",
            "settings_preflight_cached",
            "environment_preflight_cached",
        }
        has_runtime_cache_overrides = all(
            key in payload and payload.get(key) is not None
            for key in cache_override_keys
        )
        runtime_image = str(payload.get("runtime_image") or context.get("image") or "")
        resolved_extra_preflight_script = str(
            payload.get("resolved_extra_preflight_script")
            or context.get("extra_preflight_script")
            or ""
        )

        try:
            launch_docker_terminal_task(
                main_window=self,
                task=task,
                env=context.get("env"),
                env_id=context.get("env_id") or "",
                task_id=task_id,
                task_token=context.get("task_token") or "",
                terminal_opt=context.get("terminal_opt"),
                cmd_parts=cmd_parts,
                prompt=context.get("prompt") or "",
                command=context.get("command") or "",
                agent_cli=context.get("agent_cli") or "",
                host_codex=context.get("host_codex") or "",
                host_workdir=context.get("host_workdir") or "",
                config_extra_mounts=launch_mounts,
                image=runtime_image,
                container_name=context.get("container_name") or "",
                container_agent_dir=context.get("container_agent_dir") or "",
                container_workdir=context.get("container_workdir") or "",
                settings_preflight_script=context.get("settings_preflight_script"),
                environment_preflight_script=context.get(
                    "environment_preflight_script"
                ),
                extra_preflight_script=resolved_extra_preflight_script,
                stain=context.get("stain"),
                spinner=context.get("spinner"),
                desired_base=context.get("desired_base") or "",
                skip_image_pull=True,
                runtime_image_override=runtime_image
                if has_runtime_cache_overrides
                else None,
                system_preflight_cached_override=bool(
                    payload.get("system_preflight_cached")
                )
                if has_runtime_cache_overrides
                else None,
                desktop_preflight_cached_override=bool(
                    payload.get("desktop_preflight_cached")
                )
                if has_runtime_cache_overrides
                else None,
                settings_preflight_cached_override=bool(
                    payload.get("settings_preflight_cached")
                )
                if has_runtime_cache_overrides
                else None,
                environment_preflight_cached_override=bool(
                    payload.get("environment_preflight_cached")
                )
                if has_runtime_cache_overrides
                else None,
                desktop_preflight_script_override=resolved_extra_preflight_script
                if has_runtime_cache_overrides
                else None,
            )
        except Exception as exc:
            self._on_interactive_prep_failed(task_id, str(exc))
            return

        self._clear_interactive_prep_refs(task_id)

    def _start_interactive_finish_watch(self, task_id: str, finish_path: str) -> None:
        task_id = str(task_id or "").strip()
        finish_path = os.path.abspath(
            os.path.expanduser(str(finish_path or "").strip())
        )
        if not task_id or not finish_path:
            return

        existing = self._interactive_watch.get(task_id)
        if existing is not None:
            _, stop = existing
            stop.set()

        stop_event = threading.Event()
        self._interactive_watch[task_id] = (finish_path, stop_event)

        def _worker() -> None:
            while not stop_event.is_set():
                if os.path.exists(finish_path):
                    break
                time.sleep(0.35)
            if stop_event.is_set():
                return
            exit_code = 0
            for _ in range(6):
                try:
                    with open(finish_path, "r", encoding="utf-8") as f:
                        raw = (f.read() or "").strip().splitlines()[0] if f else ""
                    exit_code = int(raw or "0")
                    break
                except Exception:
                    time.sleep(0.2)

            # Encrypt finish file as artifact before deleting
            try:
                from agents_runner.artifacts import encrypt_artifact

                task_dict = {"id": task_id, "task_id": task_id}
                env_name = getattr(self, "_current_env_name", "unknown")

                artifact_uuid = encrypt_artifact(
                    task_dict=task_dict,
                    env_name=env_name,
                    source_path=finish_path,
                    original_filename=os.path.basename(finish_path),
                )

                if artifact_uuid:
                    logger.rprint(
                        f"[finish] Encrypted finish file as artifact: {artifact_uuid}",
                        mode="normal",
                    )
                else:
                    logger.rprint(
                        "[finish] Failed to encrypt finish file, but continuing",
                        mode="warn",
                    )
            except Exception as exc:
                logger.rprint(
                    f"[finish] Error encrypting finish file: {exc!r}", mode="error"
                )

            # Delete plaintext finish file
            try:
                if os.path.exists(finish_path):
                    os.unlink(finish_path)
                    logger.rprint(
                        f"[finish] Deleted plaintext finish file: {finish_path}",
                        mode="normal",
                    )
            except Exception as exc:
                logger.rprint(
                    f"[finish] Failed to delete finish file: {exc!r}", mode="warn"
                )

            self.interactive_finished.emit(task_id, int(exit_code))

        threading.Thread(target=_worker, daemon=True).start()
