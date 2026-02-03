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

from agents_runner.environments import WORKSPACE_CLONED
from agents_runner.environments import WORKSPACE_MOUNTED
from agents_runner.environments import save_environment
from agents_runner.environments.cleanup import cleanup_task_workspace
from agents_runner.environments.git_operations import get_git_info
from agents_runner.gh_management import is_gh_available
from agents_runner.docker_runner import DockerRunnerConfig
from agents_runner.log_format import format_log
from agents_runner.pr_metadata import ensure_github_context_file
from agents_runner.pr_metadata import github_context_host_path
from agents_runner.pr_metadata import github_context_prompt_instructions
from agents_runner.pr_metadata import GitHubContext
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
from agents_runner.environments.model import AgentInstance
from agents_runner.environments.model import AgentSelection
from agents_runner.ui.task_model import Task
from agents_runner.ui.utils import _stain_color

logger = logging.getLogger(__name__)


class _MainWindowTasksAgentMixin:
    def _clean_old_tasks(self) -> None:
        to_remove: set[str] = set()
        for task_id, task in self._tasks.items():
            status = (task.status or "").lower()
            if (
                status in {"done", "failed", "error"}
                and not task.is_active()
                and (
                    str(getattr(task, "finalization_state", "") or "").lower() == "done"
                )
            ):
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

            # Clean up task workspace (if using cloned GitHub repo)
            if task.workspace_type == WORKSPACE_CLONED and task.environment_id:
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
    ) -> str | None:
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

        # Check cooldown for selected agent
        from agents_runner.core.agent.cooldown_manager import CooldownManager
        from agents_runner.core.agent.keys import cooldown_key
        from agents_runner.ui.dialogs.cooldown_modal import (
            CooldownAction,
            CooldownModal,
        )

        cooldown_mgr = CooldownManager(self._watch_states)
        selected_cli_flags = ""
        if env and env.agent_selection and agent_instance_id:
            inst = next(
                (
                    a
                    for a in (env.agent_selection.agents or [])
                    if str(getattr(a, "agent_id", "") or "").strip()
                    == agent_instance_id
                ),
                None,
            )
            selected_cli_flags = (
                str(getattr(inst, "cli_flags", "") or "").strip() if inst else ""
            )

        cooldown_args: list[str] = []
        if selected_cli_flags:
            try:
                cooldown_args = shlex.split(selected_cli_flags)
            except ValueError:
                cooldown_args = []
        elif env and env.agent_cli_args.strip():
            try:
                cooldown_args = shlex.split(env.agent_cli_args)
            except ValueError:
                cooldown_args = []

        selected_key = cooldown_key(
            agent_cli=agent_cli,
            host_config_dir=auto_config_dir,
            agent_cli_args=cooldown_args,
        )
        watch_state = cooldown_mgr.check_cooldown(selected_key)

        # Show cooldown modal if agent is on cooldown
        if watch_state and watch_state.is_on_cooldown():
            # Get fallback agent name
            fallback_name = None
            fallback_agent = None
            if env and env.agent_selection and env.agent_selection.agent_fallbacks:
                # Find primary agent
                primary_agent = None
                if env.agent_selection.agents:
                    for agent in env.agent_selection.agents:
                        if agent.agent_cli == agent_cli:
                            primary_agent = agent
                            break

                # Get fallback
                if primary_agent:
                    fallback_id = env.agent_selection.agent_fallbacks.get(
                        primary_agent.agent_id
                    )
                    if fallback_id:
                        fallback_agent = next(
                            (
                                a
                                for a in env.agent_selection.agents
                                if a.agent_id == fallback_id
                            ),
                            None,
                        )
                        if fallback_agent:
                            fallback_name = fallback_agent.agent_cli.capitalize()

            # Show cooldown modal
            modal = CooldownModal(
                self,
                agent_name=agent_cli.capitalize(),
                watch_state=watch_state,
                fallback_agent_name=fallback_name,
            )

            modal.exec()
            action = modal.get_result()

            if action == CooldownAction.CANCEL:
                return  # Don't start task

            elif action == CooldownAction.BYPASS:
                # Clear cooldown and continue with original agent
                cooldown_mgr.clear_cooldown(selected_key)
                self._schedule_save()  # Persist cooldown clear

            elif action == CooldownAction.USE_FALLBACK:
                # Override agent for this task only (task-scoped)
                if fallback_agent:
                    agent_cli = fallback_agent.agent_cli
                    auto_config_dir = os.path.expanduser(
                        str(getattr(fallback_agent, "config_dir", "") or "").strip()
                    )
                    if not auto_config_dir:
                        auto_config_dir = self._resolve_config_dir_for_agent(
                            agent_cli=agent_cli,
                            env=env,
                            settings=self._settings_data,
                        )
                    agent_instance_id = fallback_agent.agent_id
                    # Don't modify environment, just use fallback for this task

        workspace_type = env.workspace_type if env else "none"
        effective_workdir, ready, message = self._new_task_workspace(
            env, task_id=task_id
        )
        if not ready:
            QMessageBox.warning(self, "Workspace not configured", message)
            return
        if workspace_type == WORKSPACE_CLONED:
            try:
                os.makedirs(effective_workdir, exist_ok=True)
            except Exception as exc:
                logger.error(
                    format_log(
                        "host",
                        "workspace",
                        "ERROR",
                        f"Failed to create directory {effective_workdir}: {exc}",
                    )
                )
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

        resolved_agent_selection: AgentSelection | None = None
        if env and env.agent_selection and getattr(env.agent_selection, "agents", None):
            resolved_agents: list[AgentInstance] = []
            for inst in list(env.agent_selection.agents or []):
                inst_cli = str(getattr(inst, "agent_cli", "") or "").strip()
                inst_dir = os.path.expanduser(
                    str(getattr(inst, "config_dir", "") or "").strip()
                )
                if not inst_dir:
                    inst_dir = self._resolve_config_dir_for_agent(
                        agent_cli=inst_cli,
                        env=env,
                        settings=self._settings_data,
                    )
                resolved_agents.append(
                    AgentInstance(
                        agent_id=str(getattr(inst, "agent_id", "") or "").strip()
                        or inst_cli,
                        agent_cli=inst_cli,
                        config_dir=inst_dir,
                        cli_flags=str(getattr(inst, "cli_flags", "") or "").strip(),
                    )
                )
            resolved_agent_selection = AgentSelection(
                agents=resolved_agents,
                selection_mode=str(
                    getattr(env.agent_selection, "selection_mode", "") or "round-robin"
                ),
                agent_fallbacks=dict(
                    getattr(env.agent_selection, "agent_fallbacks", {}) or {}
                ),
            )

        host_codex = os.path.expanduser(str(host_codex or "").strip())
        host_config_dir = auto_config_dir
        if agent_cli == "codex" and host_codex:
            host_config_dir = host_codex
        if not host_config_dir:
            host_config_dir = auto_config_dir

        if not self._ensure_agent_config_dir(agent_cli, host_config_dir):
            return
        self._settings_data[self._host_config_dir_key(agent_cli)] = host_config_dir

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
        desktop_cache_enabled = (
            bool(getattr(env, "cache_desktop_build", False)) if env else False
        )
        container_caching_enabled = (
            bool(getattr(env, "container_caching_enabled", False)) if env else False
        )
        cached_preflight_script = (
            str(getattr(env, "cached_preflight_script", "") or "").strip()
            if env
            else ""
        )
        # Only enable cache if desktop is enabled
        desktop_cache_enabled = desktop_cache_enabled and headless_desktop_enabled

        task = Task(
            task_id=task_id,
            prompt=prompt,
            image=image,
            host_workdir=effective_workdir,
            host_codex_dir=host_config_dir,
            environment_id=env_id,
            created_at_s=time.time(),
            status="queued",
            agent_cli=agent_cli,
            agent_instance_id=agent_instance_id,
            agent_cli_args=" ".join(agent_cli_args),
            headless_desktop_enabled=headless_desktop_enabled,
            workspace_type=workspace_type,
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

        # Save the selected branch for cloned environments
        if env and env.workspace_type == WORKSPACE_CLONED and desired_base:
            env.gh_last_base_branch = desired_base
            save_environment(env)
            # Update in-memory copy to persist across tab changes and reloads
            self._environments[env.env_id] = env

        runner_prompt = prompt
        if bool(self._settings_data.get("append_pixelarch_context") or False):
            runner_prompt = f"{runner_prompt.rstrip()}{PIXELARCH_AGENT_CONTEXT_SUFFIX}"

        # Inject git context when cloned workspace is used
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
                    f"appended {len(enabled_env_prompts)} environment prompt(s) (non-interactive)",
                ),
            )
        env_vars_for_task = dict(env.env_vars) if env else {}
        extra_mounts_for_task = list(env.extra_mounts) if env else []

        # Add host cache mount if enabled in settings
        if self._settings_data.get("mount_host_cache", False):
            host_cache = os.path.expanduser("~/.cache")
            container_cache = "/home/midori-ai/.cache"
            extra_mounts_for_task.append(f"{host_cache}:{container_cache}:rw")

        # Add cross-agent config mounts if enabled
        cross_agent_mounts = self._compute_cross_agent_config_mounts(
            env=env,
            primary_agent_cli=agent_cli,
            primary_config_dir=host_config_dir,
            settings=self._settings_data,
        )
        extra_mounts_for_task.extend(cross_agent_mounts)

        # GitHub context preparation
        # For cloned: Create empty file before clone, populate after clone completes
        # For mounted: Detect git and populate immediately if it's a git repo
        # For non-git: Skip gracefully (never fail the task)
        if env and bool(getattr(env, "gh_context_enabled", False)):
            # Detect git for mounted environments
            should_generate = False
            github_context = None

            if env.workspace_type == WORKSPACE_MOUNTED:
                # Mounted: Try to detect git repo
                folder_path = str(env.workspace_target or "").strip()
                if folder_path:
                    try:
                        git_info = get_git_info(folder_path)
                        if git_info:
                            should_generate = True
                            github_context = GitHubContext(
                                repo_url=git_info.repo_url,
                                repo_owner=git_info.repo_owner,
                                repo_name=git_info.repo_name,
                                base_branch=git_info.branch,
                                task_branch=None,
                                head_commit=git_info.commit_sha,
                            )
                            # Populate task.git immediately for mounted environments
                            task.git = {
                                "repo_url": git_info.repo_url,
                                "repo_owner": git_info.repo_owner,
                                "repo_name": git_info.repo_name,
                                "base_branch": git_info.branch,
                                "target_branch": None,
                                "head_commit": git_info.commit_sha,
                            }
                            # Also set gh_repo_root for mounted tasks
                            if folder_path and os.path.isdir(folder_path):
                                task.gh_repo_root = folder_path
                            self._on_task_log(
                                task_id,
                                format_log(
                                    "gh",
                                    "context",
                                    "INFO",
                                    f"detected git repo: {git_info.repo_url}",
                                ),
                            )
                        else:
                            self._on_task_log(
                                task_id,
                                format_log(
                                    "gh",
                                    "context",
                                    "INFO",
                                    "folder is not a git repository; skipping context",
                                ),
                            )
                    except Exception as exc:
                        logger.warning(
                            format_log(
                                "gh", "context", "WARN", f"git detection failed: {exc}"
                            )
                        )
                        self._on_task_log(
                            task_id,
                            format_log(
                                "gh",
                                "context",
                                "WARN",
                                f"git detection failed: {exc}; continuing without context",
                            ),
                        )
            elif env.workspace_type == WORKSPACE_CLONED:
                # Cloned: Will populate after clone
                should_generate = True

            # Create GitHub context file
            if should_generate:
                host_context_path = github_context_host_path(
                    os.path.dirname(self._state_path), task_id
                )
                pr_host_path = pr_metadata_host_path(
                    os.path.dirname(self._state_path), task_id
                )
                pr_container_path = pr_metadata_container_path(task_id)
                try:
                    ensure_github_context_file(
                        host_context_path,
                        task_id=task_id,
                        github_context=github_context,
                    )
                    ensure_pr_metadata_file(
                        pr_host_path,
                        task_id=task_id,
                    )
                except Exception as exc:
                    logger.error(
                        format_log(
                            "gh",
                            "context",
                            "ERROR",
                            f"failed to create GitHub context file: {exc}",
                        )
                    )
                    self._on_task_log(
                        task_id,
                        format_log(
                            "gh",
                            "context",
                            "ERROR",
                            f"failed to create GitHub context file: {exc}; continuing without context",
                        ),
                    )
                else:
                    task.gh_context_path = host_context_path
                    task.gh_pr_metadata_path = pr_host_path

                    # Only mount the PR title/body JSON into the container (agents edit this).
                    extra_mounts_for_task.append(
                        f"{pr_host_path}:{pr_container_path}:rw"
                    )

                    # Provide read-only repo context inline; do not mount the repo metadata JSON.
                    repo_url = ""
                    repo_owner = ""
                    repo_name = ""
                    base_branch = ""
                    task_branch = ""
                    head_commit = ""
                    if github_context is not None:
                        repo_url = github_context.repo_url
                        repo_owner = github_context.repo_owner or ""
                        repo_name = github_context.repo_name or ""
                        base_branch = github_context.base_branch
                        task_branch = github_context.task_branch or ""
                        head_commit = github_context.head_commit
                    else:
                        # For cloned repos, we may not know branch/commit until after clone.
                        repo_url = str(
                            getattr(env, "workspace_target", "") or ""
                        ).strip()
                        base_branch = str(desired_base or "").strip() or "auto"
                        task_branch = "(already created by runner)"
                        head_commit = "(set after clone)"

                    runner_prompt = (
                        f"{runner_prompt}"
                        f"{github_context_prompt_instructions(repo_url=repo_url, repo_owner=repo_owner, repo_name=repo_name, base_branch=base_branch, task_branch=task_branch, head_commit=head_commit)}"
                        f"{pr_metadata_prompt_instructions(pr_container_path)}"
                    )
                    # Clarify two-phase process for cloned repo environments
                    if workspace_type == WORKSPACE_CLONED:
                        self._on_task_log(
                            task_id,
                            format_log(
                                "gh",
                                "context",
                                "INFO",
                                "GitHub context enabled (host-only) and PR metadata file mounted",
                            ),
                        )
                        self._on_task_log(
                            task_id,
                            format_log(
                                "gh",
                                "context",
                                "INFO",
                                "Repository metadata will be populated after clone completes",
                            ),
                        )
                    else:
                        self._on_task_log(
                            task_id,
                            format_log(
                                "gh",
                                "context",
                                "INFO",
                                "GitHub context enabled (host-only) and PR metadata file mounted",
                            ),
                        )

        # Build config with GitHub repo info if needed
        # Get the host GitHub context path if it was created (regardless of mode)
        gh_context_file = getattr(task, "gh_context_path", None)
        gh_repo: str | None = None
        if workspace_type == WORKSPACE_CLONED and env:
            gh_repo = str(env.workspace_target or "").strip() or None

        config = DockerRunnerConfig(
            task_id=task_id,
            image=image,
            host_codex_dir=host_config_dir,
            host_workdir=effective_workdir,
            agent_cli=agent_cli,
            environment_id=env_id,
            auto_remove=True,
            pull_before_run=True,
            settings_preflight_script=settings_preflight_script,
            environment_preflight_script=environment_preflight_script,
            headless_desktop_enabled=headless_desktop_enabled,
            desktop_cache_enabled=desktop_cache_enabled,
            container_caching_enabled=container_caching_enabled,
            cached_preflight_script=cached_preflight_script or None,
            env_vars=env_vars_for_task,
            extra_mounts=extra_mounts_for_task,
            agent_cli_args=agent_cli_args,
            gh_repo=gh_repo,
            gh_prefer_gh_cli=use_host_gh,
            gh_recreate_if_needed=True,
            gh_base_branch=desired_base or None,
            gh_context_file_path=gh_context_file,
        )
        task._runner_config = config
        task._runner_prompt = runner_prompt
        task._agent_selection = resolved_agent_selection or (
            env.agent_selection if env else None
        )

        if self._can_start_new_agent_for_env(env_id):
            self._actually_start_task(task)
        else:
            self._on_task_log(
                task_id,
                format_log("queue", "slot", "INFO", "Waiting for available slot..."),
            )
            self._dashboard.upsert_task(task, stain=stain, spinner_color=spinner)
            self._schedule_save()

        self._show_dashboard()
        self._new_task.reset_for_new_run()
        return task_id

    def _actually_start_task(self, task: Task) -> None:
        config = getattr(task, "_runner_config", None)
        prompt = getattr(task, "_runner_prompt", None)
        agent_selection = getattr(task, "_agent_selection", None)
        if config is None or prompt is None:
            return

        task.status = "pulling"
        env = self._environments.get(task.environment_id)
        stain = env.color if env else None
        spinner = _stain_color(env.color) if env else None
        self._dashboard.upsert_task(task, stain=stain, spinner_color=spinner)

        # Clean up any existing bridge/thread for this task to prevent duplicate log emissions
        old_bridge = self._bridges.pop(task.task_id, None)
        old_thread = self._threads.pop(task.task_id, None)
        if old_bridge is not None:
            try:
                # Disconnect all signal connections to prevent duplicate log emissions
                old_bridge.log.disconnect()
                old_bridge.state.disconnect()
                old_bridge.done.disconnect()
                old_bridge.retry_attempt.disconnect()
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
            task_id=task.task_id,
            config=config,
            prompt=prompt,
            agent_selection=agent_selection,
            watch_states=self._watch_states,
        )
        thread = QThread(self)
        bridge.moveToThread(thread)
        thread.started.connect(bridge.run)

        bridge.state.connect(self._on_bridge_state, Qt.QueuedConnection)
        bridge.log.connect(self._on_bridge_log, Qt.QueuedConnection)
        bridge.done.connect(self._on_bridge_done, Qt.QueuedConnection)
        bridge.retry_attempt.connect(self._on_bridge_retry_attempt, Qt.QueuedConnection)
        bridge.agent_switched.connect(
            self._on_bridge_agent_switched, Qt.QueuedConnection
        )

        bridge.done.connect(thread.quit, Qt.QueuedConnection)
        bridge.done.connect(bridge.deleteLater, Qt.QueuedConnection)
        thread.finished.connect(thread.deleteLater)

        self._bridges[task.task_id] = bridge
        self._threads[task.task_id] = thread
        self._run_started_s[task.task_id] = time.time()

        thread.start()
        self._schedule_save()
