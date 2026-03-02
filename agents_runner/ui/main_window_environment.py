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
from agents_runner.ide_systems import get_default_ide_system_name


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

    def _refresh_active_environment_repo_branches(
        self,
        *,
        trigger_reason: str,
        show_loading_ui: bool,
        preserve_current_selection: bool,
    ) -> None:
        env = self._environments.get(self._active_environment_id())
        self._sync_new_task_repo_controls(
            env,
            trigger_reason=trigger_reason,
            show_loading_ui=show_loading_ui,
            preserve_current_selection=preserve_current_selection,
        )

    def _sync_new_task_repo_controls(
        self,
        env: Environment | None,
        *,
        trigger_reason: str = "environment_apply",
        show_loading_ui: bool = False,
        preserve_current_selection: bool = False,
    ) -> None:
        _workdir, ready, _ = self._new_task_workspace(env)
        if not ready:
            self._new_task.set_repo_branches_loading(False)
            self._new_task.set_repo_controls_visible(False)
            self._new_task.set_repo_branches([])
            return

        workspace_type = env.workspace_type or WORKSPACE_NONE if env else WORKSPACE_NONE
        has_repo = bool(workspace_type == WORKSPACE_CLONED)
        if workspace_type == WORKSPACE_NONE or not has_repo:
            self._new_task.set_repo_branches_loading(False)
            self._new_task.set_repo_controls_visible(False)
            self._new_task.set_repo_branches([])
            return

        self._new_task.set_repo_controls_visible(True)

        if workspace_type == WORKSPACE_CLONED and env:
            target = str(env.workspace_target or "").strip()
            if not target:
                self._new_task.set_repo_branches_loading(False)
                self._new_task.set_repo_branches([])
                return
            env_id = str(env.env_id or "").strip()
            fallback_branches = list(
                getattr(self, "_repo_branches_cache", {}).get(env_id, [])
            )
            fallback_selected = ""
            last_branch = str(getattr(env, "gh_last_base_branch", "") or "").strip()
            if last_branch and last_branch in fallback_branches:
                fallback_selected = last_branch

            normalized_reason = str(trigger_reason or "").strip().lower()
            if show_loading_ui:
                if normalized_reason == "env_switch":
                    if fallback_branches:
                        self._new_task.set_repo_branches(
                            fallback_branches,
                            selected=fallback_selected or None,
                            preserve_current_selection=False,
                        )
                    else:
                        self._new_task.set_repo_branches([])
                self._new_task.set_repo_branches_loading(True)
            else:
                self._new_task.set_repo_branches_loading(False)

            self._repo_branches_request_id += 1
            request_id = int(self._repo_branches_request_id)
            self._repo_branches_request_meta[request_id] = {
                "env_id": env_id,
                "trigger_reason": str(trigger_reason or "").strip(),
                "preserve_current_selection": bool(preserve_current_selection),
                "fallback_branches": fallback_branches,
                "fallback_selected": fallback_selected,
            }

            def _worker() -> None:
                result: object
                try:
                    result = git_list_remote_heads(target)
                except Exception:
                    result = None
                try:
                    self.repo_branches_ready.emit(request_id, result)
                except Exception:
                    pass

            threading.Thread(target=_worker, daemon=True).start()

    def _on_repo_branches_ready(self, request_id: int, branches: object) -> None:
        try:
            request_id = int(request_id)
        except Exception:
            return
        if request_id != int(getattr(self, "_repo_branches_request_id", 0)):
            self._repo_branches_request_meta.pop(request_id, None)
            return
        request_meta = self._repo_branches_request_meta.pop(request_id, {})

        preserve_current_selection = bool(
            request_meta.get("preserve_current_selection")
        )
        fallback_branch_values = request_meta.get("fallback_branches", [])
        fallback_branches = [
            str(branch or "").strip()
            for branch in fallback_branch_values
            if str(branch or "").strip()
        ]
        fallback_selected_raw = str(request_meta.get("fallback_selected") or "").strip()
        fallback_selected = fallback_selected_raw if fallback_selected_raw else None

        env = self._environments.get(self._active_environment_id())
        workspace_type = env.workspace_type or WORKSPACE_NONE if env else WORKSPACE_NONE
        if workspace_type != WORKSPACE_CLONED:
            self._new_task.set_repo_branches_loading(False)
            return
        if not isinstance(branches, list):
            if fallback_branches:
                self._new_task.set_repo_branches(
                    fallback_branches,
                    selected=fallback_selected,
                    preserve_current_selection=preserve_current_selection,
                )
            else:
                self._new_task.set_repo_branches_loading(False)
            return
        cleaned = [str(b or "").strip() for b in branches]
        cleaned = [b for b in cleaned if b]
        if not cleaned:
            if fallback_branches:
                self._new_task.set_repo_branches(
                    fallback_branches,
                    selected=fallback_selected,
                    preserve_current_selection=preserve_current_selection,
                )
            else:
                self._new_task.set_repo_branches_loading(False)
            return
        self._new_task.set_repo_controls_visible(True)

        # Restore last selected branch for cloned environments
        selected_branch = None
        if env and env.workspace_type == WORKSPACE_CLONED:
            last_branch = str(getattr(env, "gh_last_base_branch", "") or "").strip()
            if last_branch and last_branch in cleaned:
                selected_branch = last_branch

        env_id = str(env.env_id or "").strip() if env else ""
        if env_id:
            self._repo_branches_cache[env_id] = list(cleaned)
        self._new_task.set_repo_branches(
            cleaned,
            selected=selected_branch,
            preserve_current_selection=preserve_current_selection,
        )

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
        ide_system_overrides = {
            e.env_id: str(getattr(e, "ide_system_override", "") or "").strip()
            for e in envs
        }

        self._new_task.set_environment_stains(stains)
        self._new_task.set_environment_workspace_types(workspace_types)
        self._new_task.set_environment_template_injection_status(template_statuses)
        self._new_task.set_environment_desktop_enabled(desktop_enabled)
        self._new_task.set_environment_ide_overrides(
            ide_system_overrides=ide_system_overrides,
        )
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

    def _apply_active_environment_to_new_task(
        self,
        *,
        branch_refresh_reason: str = "environment_apply",
        show_branch_loading: bool = False,
        preserve_branch_selection: bool = False,
    ) -> None:
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

        env_agents = {
            env_id: list(getattr(env_data.agent_selection, "agents", []) or [])
            for env_id, env_data in self._environments.items()
        }
        self._new_task.set_environment_agents(env_agents)
        self._new_task.set_defaults(host_codex=host_codex)
        self._new_task.set_workspace_status(path=workdir, ready=ready, message=message)
        self._new_task.set_agent_info(agent=current_agent, next_agent=next_agent)
        self._sync_new_task_repo_controls(
            env,
            trigger_reason=branch_refresh_reason,
            show_loading_ui=show_branch_loading,
            preserve_current_selection=preserve_branch_selection,
        )
        self._new_task.set_interactive_defaults(
            terminal_id=str(self._settings_data.get("interactive_terminal_id") or ""),
            command=self._default_interactive_command(agent_cli),
        )
        self._new_task.set_ide_defaults(
            ide_system=str(
                self._settings_data.get("ide_system_default")
                or get_default_ide_system_name()
            ),
        )
        self._populate_environment_pickers()
        if hasattr(self, "_radio_controller") and hasattr(
            self, "_update_window_title_from_radio_state"
        ):
            try:
                self._update_window_title_from_radio_state(
                    self._radio_controller.state_snapshot()
                )
            except Exception:
                pass

    def _on_new_task_env_changed(self, env_id: str) -> None:
        if self._syncing_environment:
            return
        env_id = str(env_id or "")
        if env_id and env_id in self._environments:
            self._settings_data["active_environment_id"] = env_id
            self._apply_active_environment_to_new_task(
                branch_refresh_reason="env_switch",
                show_branch_loading=True,
                preserve_branch_selection=False,
            )
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
