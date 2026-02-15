from __future__ import annotations

import os
import threading


from agents_runner.environments import Environment
from agents_runner.environments import WORKSPACE_CLONED
from agents_runner.environments import WORKSPACE_MOUNTED
from agents_runner.environments import WORKSPACE_NONE
from agents_runner.environments import SYSTEM_ENV_ID
from agents_runner.environments import SYSTEM_ENV_NAME
from agents_runner.environments import load_environments
from agents_runner.environments import managed_repo_checkout_path
from agents_runner.environments import save_environment
from agents_runner.gh_management import git_list_remote_heads
from agents_runner.gh_management import is_gh_available


class MainWindowEnvironmentMixin:
    @staticmethod
    def _is_internal_environment_id(env_id: str) -> bool:
        return str(env_id or "").strip() == SYSTEM_ENV_ID

    def _active_environment_id(self) -> str:
        return str(self._settings_data.get("active_environment_id") or "default")

    def _user_environment_map(self) -> dict[str, Environment]:
        return {
            env.env_id: env
            for env in self._environments.values()
            if not self._is_internal_environment_id(env.env_id)
        }

    def _environment_list(self) -> list[Environment]:
        return sorted(
            self._user_environment_map().values(),
            key=lambda e: (e.name or e.env_id).lower(),
        )

    def _environment_effective_workdir(
        self, env: Environment | None, fallback: str
    ) -> str:
        fallback = os.path.expanduser(str(fallback or "").strip()) or os.getcwd()
        if env is None:
            return fallback
        workspace_type = env.workspace_type or WORKSPACE_NONE
        if workspace_type == WORKSPACE_MOUNTED:
            return os.path.expanduser(str(env.workspace_target or "").strip())
        if workspace_type == WORKSPACE_CLONED:
            workdir = managed_repo_checkout_path(
                env.env_id, data_dir=os.path.dirname(self._state_path)
            )
            try:
                os.makedirs(workdir, exist_ok=True)
            except Exception:
                pass
            return workdir
        return fallback

    def _new_task_workspace(
        self, env: Environment | None, task_id: str | None = None
    ) -> tuple[str, bool, str]:
        if env is None:
            return "—", False, "Pick an environment first."

        workspace_type = env.workspace_type or WORKSPACE_NONE
        if workspace_type == WORKSPACE_MOUNTED:
            path = os.path.expanduser(str(env.workspace_target or "").strip())
            if not path:
                return "—", False, "Set Workspace to a local folder in Environments."
            if not os.path.isdir(path):
                return path, False, f"Local folder does not exist: {path}"
            return path, True, ""

        if workspace_type == WORKSPACE_CLONED:
            path = managed_repo_checkout_path(
                env.env_id,
                data_dir=os.path.dirname(self._state_path),
                task_id=task_id,
            )
            target = str(env.workspace_target or "").strip()
            if not target:
                return path, False, "Set Workspace to a GitHub repo in Environments."
            return path, True, ""

        return (
            "—",
            False,
            "Set Workspace to a local folder or GitHub repo in Environments.",
        )

    def _sync_new_task_repo_controls(self, env: Environment | None) -> None:
        _workdir, ready, _ = self._new_task_workspace(env)
        if not ready:
            self._new_task.set_repo_controls_visible(False)
            self._new_task.set_repo_branches([])
            return

        workspace_type = env.workspace_type or WORKSPACE_NONE if env else WORKSPACE_NONE
        has_repo = bool(workspace_type == WORKSPACE_CLONED)
        if workspace_type == WORKSPACE_NONE or not has_repo:
            self._new_task.set_repo_controls_visible(False)
            self._new_task.set_repo_branches([])
            return

        self._new_task.set_repo_controls_visible(True)
        self._new_task.set_repo_branches([])

        if workspace_type == WORKSPACE_CLONED and env:
            target = str(env.workspace_target or "").strip()
            if not target:
                return
            self._repo_branches_request_id += 1
            request_id = int(self._repo_branches_request_id)

            def _worker() -> None:
                branches = git_list_remote_heads(target)
                try:
                    self.repo_branches_ready.emit(request_id, branches)
                except Exception:
                    pass

            threading.Thread(target=_worker, daemon=True).start()

    def _on_repo_branches_ready(self, request_id: int, branches: object) -> None:
        try:
            request_id = int(request_id)
        except Exception:
            return
        if request_id != int(getattr(self, "_repo_branches_request_id", 0)):
            return
        env = self._environments.get(self._active_environment_id())
        workspace_type = env.workspace_type or WORKSPACE_NONE if env else WORKSPACE_NONE
        if workspace_type != WORKSPACE_CLONED:
            return
        if not isinstance(branches, list):
            return
        cleaned = [str(b or "").strip() for b in branches]
        cleaned = [b for b in cleaned if b]
        self._new_task.set_repo_controls_visible(True)

        # Restore last selected branch for cloned environments
        selected_branch = None
        if env and env.workspace_type == WORKSPACE_CLONED:
            last_branch = str(getattr(env, "gh_last_base_branch", "") or "").strip()
            if last_branch and last_branch in cleaned:
                selected_branch = last_branch

        self._new_task.set_repo_branches(cleaned, selected=selected_branch)

    def _populate_environment_pickers(self) -> None:
        active_id = self._active_environment_id()
        envs = self._environment_list()
        disk_envs = load_environments()
        stains = {e.env_id: e.color for e in envs}
        workspace_types = {e.env_id: e.workspace_type or WORKSPACE_NONE for e in envs}
        template_statuses = {
            e.env_id: bool(
                getattr(
                    disk_envs.get(e.env_id) or e, "midoriai_template_detected", False
                )
            )
            for e in envs
        }
        desktop_enabled = {
            e.env_id: (
                e.headless_desktop_enabled
                or self._settings_data.get("headless_desktop_enabled", False)
            )
            for e in envs
        }

        self._new_task.set_environment_stains(stains)
        self._new_task.set_environment_workspace_types(workspace_types)
        self._new_task.set_environment_template_injection_status(template_statuses)
        self._new_task.set_environment_desktop_enabled(desktop_enabled)
        self._dashboard.set_environment_filter_options(
            [(e.env_id, e.name or e.env_id) for e in envs]
        )
        if hasattr(self, "_tasks_page"):
            self._tasks_page.set_environments(self._user_environment_map(), active_id)

        self._syncing_environment = True
        try:
            self._new_task.set_environments(
                [(e.env_id, e.name or e.env_id) for e in envs], active_id=active_id
            )
            self._new_task.set_environment_id(active_id)
        finally:
            self._syncing_environment = False

    def _apply_active_environment_to_new_task(self) -> None:
        env = self._environments.get(self._active_environment_id())
        # Get effective agent and config dir (environment agent_selection overrides settings)
        agent_cli, host_codex = self._effective_agent_and_config(env=env)
        if hasattr(self, "_root"):
            try:
                from agents_runner.ui.graphics import normalize_ui_theme_name

                ui_theme = normalize_ui_theme_name(
                    self._settings_data.get("ui_theme"), allow_auto=True
                )
                if ui_theme == "auto":
                    self._root.set_agent_theme(agent_cli)
                else:
                    self._root.set_theme_name(ui_theme)
            except Exception:
                pass
        current_agent, next_agent = self._get_next_agent_info(env=env)
        workdir, ready, message = self._new_task_workspace(env)

        workspace_type = env.workspace_type or WORKSPACE_NONE if env else WORKSPACE_NONE
        if (
            env
            and ready
            and workspace_type == WORKSPACE_MOUNTED
            and os.path.isdir(workdir)
        ):
            try:
                from agents_runner.environments.midoriai_template import (
                    apply_midoriai_template_detection,
                )

                apply_midoriai_template_detection(env, workspace_root=workdir)
                save_environment(env)
                self._environments[env.env_id] = env
            except Exception:
                pass

        self._new_task.set_defaults(host_codex=host_codex)
        self._new_task.set_workspace_status(path=workdir, ready=ready, message=message)
        self._new_task.set_agent_info(agent=current_agent, next_agent=next_agent)
        self._sync_new_task_repo_controls(env)
        self._new_task.set_interactive_defaults(
            terminal_id=str(self._settings_data.get("interactive_terminal_id") or ""),
            command=self._default_interactive_command(agent_cli),
        )
        self._populate_environment_pickers()

    def _on_new_task_env_changed(self, env_id: str) -> None:
        if self._syncing_environment:
            return
        env_id = str(env_id or "")
        if env_id and env_id in self._environments:
            self._settings_data["active_environment_id"] = env_id
            self._apply_active_environment_to_new_task()
            self._schedule_save()

    def _reload_environments(self, preferred_env_id: str = "") -> None:
        envs = load_environments()
        if not envs:
            active_workdir = str(self._settings_data.get("host_workdir") or os.getcwd())
            active_codex = str(
                self._settings_data.get("host_codex_dir")
                or os.path.expanduser("~/.codex")
            )
            try:
                max_agents_running = int(
                    str(self._settings_data.get("max_agents_running", -1)).strip()
                )
            except Exception:
                max_agents_running = -1
            env = Environment(
                env_id="default",
                name="Default",
                color="emerald",
                host_workdir="",
                host_codex_dir=active_codex,
                max_agents_running=max_agents_running,
                preflight_enabled=False,
                preflight_script="",
                gh_management_locked=True,
                workspace_type=WORKSPACE_MOUNTED,
                workspace_target=os.path.expanduser(active_workdir),
                gh_use_host_cli=bool(is_gh_available()),
            )
            save_environment(env)
            envs = load_environments()

        if SYSTEM_ENV_ID not in envs:
            envs[SYSTEM_ENV_ID] = Environment(
                env_id=SYSTEM_ENV_ID,
                name=SYSTEM_ENV_NAME,
                color="slate",
                host_workdir="",
                host_codex_dir="",
                max_agents_running=-1,
                preflight_enabled=False,
                preflight_script="",
                gh_management_locked=True,
                workspace_type=WORKSPACE_NONE,
                workspace_target="",
                gh_use_host_cli=False,
            )

        for env in envs.values():
            workspace_type = env.workspace_type or WORKSPACE_NONE
            if workspace_type != WORKSPACE_NONE:
                continue
            legacy_workdir = os.path.expanduser(str(env.host_workdir or "").strip())
            if legacy_workdir:
                env.gh_management_locked = True
                env.workspace_type = WORKSPACE_MOUNTED
                env.workspace_target = legacy_workdir

        self._environments = dict(envs)
        active_id = self._active_environment_id()
        if self._is_internal_environment_id(active_id):
            active_id = "default"
            self._settings_data["active_environment_id"] = active_id
        if active_id not in self._environments:
            if "default" in self._environments:
                self._settings_data["active_environment_id"] = "default"
            else:
                ordered = self._environment_list()
                if ordered:
                    self._settings_data["active_environment_id"] = ordered[0].env_id
        for task in self._tasks.values():
            if not task.environment_id:
                task.environment_id = self._active_environment_id()
        if self._envs_page.isVisible():
            current_selected = self._envs_page.selected_environment_id()
            selected = (
                preferred_env_id or current_selected or self._active_environment_id()
            )
            if self._is_internal_environment_id(selected):
                selected = self._active_environment_id()
            if not (preferred_env_id and preferred_env_id == current_selected):
                self._envs_page.set_environments(self._user_environment_map(), selected)
        self._apply_active_environment_to_new_task()
        self._refresh_task_rows()
        self._schedule_save()
