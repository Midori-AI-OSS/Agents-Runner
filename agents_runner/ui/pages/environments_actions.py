from __future__ import annotations


from dataclasses import replace

from PySide6.QtWidgets import QMessageBox

from agents_runner.environments import Environment
from agents_runner.environments import WORKSPACE_CLONED
from agents_runner.environments import WORKSPACE_MOUNTED
from agents_runner.environments import WORKSPACE_NONE
from agents_runner.environments import delete_environment
from agents_runner.environments import load_environments
from agents_runner.environments import save_environment
from agents_runner.gh_management import is_gh_available
from agents_runner.ui.dialogs.new_environment_wizard import NewEnvironmentWizard
from agents_runner.ui.pages.github_trust import normalize_trusted_mode


class _EnvironmentsPageActionsMixin:
    def _sync_workspace_controls(
        self, *_: object, env: Environment | None = None
    ) -> None:
        if env is None:
            env = self._environments.get(str(self._current_env_id or ""))

        gh_available = bool(is_gh_available())
        workspace_type = str(self._workspace_type_combo.currentData() or WORKSPACE_NONE)
        locked = env is not None

        if locked and env is not None:
            # Sync UI to match environment's workspace_type
            desired_workspace_type = env.workspace_type or WORKSPACE_NONE

            if desired_workspace_type != workspace_type:
                idx = self._workspace_type_combo.findData(desired_workspace_type)
                if idx >= 0:
                    self._workspace_type_combo.blockSignals(True)
                    try:
                        self._workspace_type_combo.setCurrentIndex(idx)
                    finally:
                        self._workspace_type_combo.blockSignals(False)
                workspace_type = desired_workspace_type

            desired_target = str(env.workspace_target or "")
            if (self._workspace_target.text() or "") != desired_target:
                self._workspace_target.blockSignals(True)
                try:
                    self._workspace_target.setText(desired_target)
                finally:
                    self._workspace_target.blockSignals(False)

            desired_gh = bool(getattr(env, "gh_use_host_cli", True))
            if bool(self._gh_use_host_cli.isChecked()) != desired_gh:
                self._gh_use_host_cli.blockSignals(True)
                try:
                    self._gh_use_host_cli.setChecked(desired_gh)
                finally:
                    self._gh_use_host_cli.blockSignals(False)

        self._workspace_type_combo.setEnabled(not locked)
        self._workspace_target.setEnabled(not locked)
        self._gh_use_host_cli.setVisible(False)
        self._gh_use_host_cli.setEnabled(not locked and gh_available)
        if not gh_available:
            self._gh_use_host_cli.setChecked(False)

        wants_browse = workspace_type == WORKSPACE_MOUNTED
        self._gh_management_browse.setVisible(False)
        self._gh_management_browse.setEnabled(wants_browse and not locked)

    def _on_new(self) -> None:
        wizard = NewEnvironmentWizard(self)
        wizard.environment_created.connect(lambda env: self.updated.emit(env.env_id))
        wizard.exec()

    def _on_delete(self) -> None:
        env_id = self._current_env_id
        env = self._environments.get(env_id or "")
        if not env:
            return
        confirm = QMessageBox.question(
            self,
            "Delete environment",
            f"Delete environment '{env.name}'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return
        delete_environment(env.env_id)
        self.updated.emit("")

    def try_autosave(
        self,
        *,
        preferred_env_id: str | None = None,
        show_validation_errors: bool = True,
    ) -> bool:
        for timer_name in ("_autosave_timer", "_advanced_autosave_timer"):
            autosave_timer = getattr(self, timer_name, None)
            if autosave_timer is not None and autosave_timer.isActive():
                autosave_timer.stop()

        if bool(getattr(self, "_suppress_autosave", False)):
            return True

        env_id = self._current_env_id
        if not env_id:
            return True
        name = (self._name.text() or "").strip()
        if not name:
            if show_validation_errors:
                QMessageBox.warning(
                    self, "Missing name", "Enter an environment name first."
                )
            return False

        existing = self._environments.get(env_id)
        disk_existing = load_environments().get(env_id)
        base_env = disk_existing or existing
        max_agents_text = str(self._max_agents_running.text() or "-1").strip()
        try:
            max_agents_running = int(max_agents_text)
        except ValueError:
            max_agents_running = -1

        # Get workspace type and target from existing environment
        workspace_type = (
            existing.workspace_type or WORKSPACE_NONE if existing else WORKSPACE_NONE
        )
        workspace_target = (
            str(existing.workspace_target or "").strip() if existing else ""
        )
        gh_locked = True
        gh_use_host_cli = (
            bool(getattr(existing, "gh_use_host_cli", True)) if existing else False
        )
        gh_context_enabled = (
            bool(getattr(existing, "gh_context_enabled", False)) if existing else False
        )

        if existing and workspace_type == WORKSPACE_CLONED:
            gh_context_enabled = bool(self._gh_context_enabled.isChecked())
        elif existing and workspace_type == WORKSPACE_MOUNTED:
            # For mounted folders, respect checkbox if git was detected
            is_git_repo = existing.detect_git_if_mounted_folder()
            if is_git_repo:
                gh_context_enabled = bool(self._gh_context_enabled.isChecked())
            else:
                gh_context_enabled = False
        else:
            gh_context_enabled = False
        github_polling_enabled = bool(self._github_polling_enabled.isChecked())
        agentsnova_trusted_mode = normalize_trusted_mode(
            self._agentsnova_trusted_mode.currentData() or "inherit"
        )
        agentsnova_trusted_users_env = (
            self._agentsnova_trusted_users_env.get_usernames()
        )

        env_vars, errors = self._env_vars_tab.get_env_vars()
        if errors:
            if show_validation_errors:
                QMessageBox.warning(
                    self, "Invalid env vars", "Fix env vars:\n" + "\n".join(errors[:12])
                )
            return False

        mounts, mount_errors = self._mounts_tab.get_mounts()
        if mount_errors:
            if show_validation_errors:
                QMessageBox.warning(
                    self,
                    "Invalid mounts",
                    "Fix mounts:\n" + "\n".join(mount_errors[:12]),
                )
            return False
        env_vars_advanced_mode = bool(self._env_vars_tab.is_advanced_mode())
        mounts_advanced_mode = bool(self._mounts_tab.is_advanced_mode())
        env_vars_advanced_acknowledged = bool(
            self._env_vars_tab.is_advanced_acknowledged()
        )
        mounts_advanced_acknowledged = bool(self._mounts_tab.is_advanced_acknowledged())
        ports, ports_unlocked, ports_advanced_acknowledged, port_errors = (
            self._ports_tab.get_ports()
        )
        if port_errors:
            if show_validation_errors:
                QMessageBox.warning(
                    self, "Invalid ports", "Fix ports:\n" + "\n".join(port_errors[:12])
                )
            return False
        prompts, prompts_unlocked = self._prompts_tab.get_prompts()
        agent_selection = self._agents_tab.get_agent_selection()

        # Read cross-agents configuration
        use_cross_agents = bool(self._use_cross_agents.isChecked())
        cross_agent_allowlist = self._agents_tab.get_cross_agent_allowlist()

        preflight_enabled = bool(self._preflight_enabled.isChecked())
        preflight_script = str(self._preflight_script.toPlainText() or "")
        cache_system_preflight_enabled = bool(
            self._cache_system_preflight_enabled.isChecked()
        )
        cache_settings_preflight_enabled = bool(
            self._cache_settings_preflight_enabled.isChecked()
        )

        if base_env is None:
            env = Environment(
                env_id=env_id,
                name=name,
                color=str(self._color.currentData() or "slate"),
                host_workdir="",
                max_agents_running=max_agents_running,
                headless_desktop_enabled=bool(
                    self._headless_desktop_enabled.isChecked()
                ),
                cache_desktop_build=bool(self._cache_desktop_build.isChecked()),
                container_caching_enabled=bool(
                    self._container_caching_enabled.isChecked()
                ),
                cache_system_preflight_enabled=cache_system_preflight_enabled,
                cache_settings_preflight_enabled=cache_settings_preflight_enabled,
                preflight_enabled=preflight_enabled,
                preflight_script=preflight_script,
                env_vars=env_vars,
                extra_mounts=mounts,
                env_vars_advanced_mode=env_vars_advanced_mode,
                mounts_advanced_mode=mounts_advanced_mode,
                env_vars_advanced_acknowledged=env_vars_advanced_acknowledged,
                mounts_advanced_acknowledged=mounts_advanced_acknowledged,
                ports=ports,
                ports_unlocked=ports_unlocked,
                ports_advanced_acknowledged=ports_advanced_acknowledged,
                gh_management_locked=gh_locked,
                workspace_type=workspace_type,
                workspace_target=workspace_target,
                gh_use_host_cli=gh_use_host_cli,
                gh_context_enabled=gh_context_enabled,
                github_polling_enabled=github_polling_enabled,
                agentsnova_trusted_users_env=agentsnova_trusted_users_env,
                agentsnova_trusted_mode=agentsnova_trusted_mode,
                prompts=prompts,
                prompts_unlocked=prompts_unlocked,
                agent_selection=agent_selection,
                use_cross_agents=use_cross_agents,
                cross_agent_allowlist=cross_agent_allowlist,
            )
        else:
            env = replace(
                base_env,
                name=name,
                color=str(self._color.currentData() or "slate"),
                max_agents_running=max_agents_running,
                headless_desktop_enabled=bool(
                    self._headless_desktop_enabled.isChecked()
                ),
                cache_desktop_build=bool(self._cache_desktop_build.isChecked()),
                container_caching_enabled=bool(
                    self._container_caching_enabled.isChecked()
                ),
                cache_system_preflight_enabled=cache_system_preflight_enabled,
                cache_settings_preflight_enabled=cache_settings_preflight_enabled,
                preflight_enabled=preflight_enabled,
                preflight_script=preflight_script,
                env_vars=env_vars,
                extra_mounts=mounts,
                env_vars_advanced_mode=env_vars_advanced_mode,
                mounts_advanced_mode=mounts_advanced_mode,
                env_vars_advanced_acknowledged=env_vars_advanced_acknowledged,
                mounts_advanced_acknowledged=mounts_advanced_acknowledged,
                ports=ports,
                ports_unlocked=ports_unlocked,
                ports_advanced_acknowledged=ports_advanced_acknowledged,
                gh_management_locked=gh_locked,
                workspace_type=workspace_type,
                workspace_target=workspace_target,
                gh_use_host_cli=gh_use_host_cli,
                gh_context_enabled=gh_context_enabled,
                github_polling_enabled=github_polling_enabled,
                agentsnova_trusted_users_env=agentsnova_trusted_users_env,
                agentsnova_trusted_mode=agentsnova_trusted_mode,
                prompts=prompts,
                prompts_unlocked=prompts_unlocked,
                agent_selection=agent_selection,
                use_cross_agents=use_cross_agents,
                cross_agent_allowlist=cross_agent_allowlist,
            )
        save_environment(env)
        self.updated.emit(preferred_env_id if preferred_env_id is not None else env_id)
        return True

    def selected_environment_id(self) -> str:
        return str(self._env_select.currentData() or "")

    def _draft_environment_from_form(self) -> Environment | None:
        env_id = self._current_env_id
        if not env_id:
            return None

        existing = self._environments.get(env_id)
        max_agents_text = str(self._max_agents_running.text() or "-1").strip()
        try:
            max_agents_running = int(max_agents_text)
        except ValueError:
            max_agents_running = -1

        # Get workspace type and target from existing environment
        workspace_type = (
            existing.workspace_type or WORKSPACE_NONE if existing else WORKSPACE_NONE
        )
        workspace_target = (
            str(existing.workspace_target or "").strip() if existing else ""
        )
        gh_locked = True
        gh_use_host_cli = (
            bool(getattr(existing, "gh_use_host_cli", True)) if existing else False
        )
        gh_context_enabled = (
            bool(getattr(existing, "gh_context_enabled", False)) if existing else False
        )

        if existing and workspace_type == WORKSPACE_CLONED:
            gh_context_enabled = bool(self._gh_context_enabled.isChecked())
        elif existing and workspace_type == WORKSPACE_MOUNTED:
            # For mounted folders, respect checkbox if git was detected
            is_git_repo = existing.detect_git_if_mounted_folder()
            if is_git_repo:
                gh_context_enabled = bool(self._gh_context_enabled.isChecked())
            else:
                gh_context_enabled = False
        else:
            gh_context_enabled = False
        github_polling_enabled = bool(self._github_polling_enabled.isChecked())
        agentsnova_trusted_mode = normalize_trusted_mode(
            self._agentsnova_trusted_mode.currentData() or "inherit"
        )
        agentsnova_trusted_users_env = (
            self._agentsnova_trusted_users_env.get_usernames()
        )

        env_vars, errors = self._env_vars_tab.get_env_vars()
        if errors:
            QMessageBox.warning(
                self, "Invalid env vars", "Fix env vars:\n" + "\n".join(errors[:12])
            )
            return None

        mounts, mount_errors = self._mounts_tab.get_mounts()
        if mount_errors:
            QMessageBox.warning(
                self, "Invalid mounts", "Fix mounts:\n" + "\n".join(mount_errors[:12])
            )
            return None
        env_vars_advanced_mode = bool(self._env_vars_tab.is_advanced_mode())
        mounts_advanced_mode = bool(self._mounts_tab.is_advanced_mode())
        env_vars_advanced_acknowledged = bool(
            self._env_vars_tab.is_advanced_acknowledged()
        )
        mounts_advanced_acknowledged = bool(self._mounts_tab.is_advanced_acknowledged())
        ports, ports_unlocked, ports_advanced_acknowledged, port_errors = (
            self._ports_tab.get_ports()
        )
        if port_errors:
            QMessageBox.warning(
                self, "Invalid ports", "Fix ports:\n" + "\n".join(port_errors[:12])
            )
            return None
        name = (self._name.text() or "").strip() or env_id
        prompts, prompts_unlocked = self._prompts_tab.get_prompts()
        agent_selection = self._agents_tab.get_agent_selection()

        # Read cross-agents configuration
        use_cross_agents = bool(self._use_cross_agents.isChecked())
        cross_agent_allowlist = self._agents_tab.get_cross_agent_allowlist()

        preflight_enabled = bool(self._preflight_enabled.isChecked())
        preflight_script = str(self._preflight_script.toPlainText() or "")
        cache_system_preflight_enabled = bool(
            self._cache_system_preflight_enabled.isChecked()
        )
        cache_settings_preflight_enabled = bool(
            self._cache_settings_preflight_enabled.isChecked()
        )

        if existing is None:
            return Environment(
                env_id=env_id,
                name=name,
                color=str(self._color.currentData() or "slate"),
                host_workdir="",
                max_agents_running=max_agents_running,
                headless_desktop_enabled=bool(
                    self._headless_desktop_enabled.isChecked()
                ),
                cache_desktop_build=bool(self._cache_desktop_build.isChecked()),
                container_caching_enabled=bool(
                    self._container_caching_enabled.isChecked()
                ),
                cache_system_preflight_enabled=cache_system_preflight_enabled,
                cache_settings_preflight_enabled=cache_settings_preflight_enabled,
                preflight_enabled=preflight_enabled,
                preflight_script=preflight_script,
                env_vars=env_vars,
                extra_mounts=mounts,
                env_vars_advanced_mode=env_vars_advanced_mode,
                mounts_advanced_mode=mounts_advanced_mode,
                env_vars_advanced_acknowledged=env_vars_advanced_acknowledged,
                mounts_advanced_acknowledged=mounts_advanced_acknowledged,
                ports=ports,
                ports_unlocked=ports_unlocked,
                ports_advanced_acknowledged=ports_advanced_acknowledged,
                gh_management_locked=gh_locked,
                workspace_type=workspace_type,
                workspace_target=workspace_target,
                gh_use_host_cli=gh_use_host_cli,
                gh_context_enabled=gh_context_enabled,
                github_polling_enabled=github_polling_enabled,
                agentsnova_trusted_users_env=agentsnova_trusted_users_env,
                agentsnova_trusted_mode=agentsnova_trusted_mode,
                prompts=prompts,
                prompts_unlocked=prompts_unlocked,
                agent_selection=agent_selection,
                use_cross_agents=use_cross_agents,
                cross_agent_allowlist=cross_agent_allowlist,
            )

        return replace(
            existing,
            name=name,
            color=str(self._color.currentData() or "slate"),
            max_agents_running=max_agents_running,
            headless_desktop_enabled=bool(self._headless_desktop_enabled.isChecked()),
            cache_desktop_build=bool(self._cache_desktop_build.isChecked()),
            container_caching_enabled=bool(self._container_caching_enabled.isChecked()),
            cache_system_preflight_enabled=cache_system_preflight_enabled,
            cache_settings_preflight_enabled=cache_settings_preflight_enabled,
            preflight_enabled=preflight_enabled,
            preflight_script=preflight_script,
            env_vars=env_vars,
            extra_mounts=mounts,
            env_vars_advanced_mode=env_vars_advanced_mode,
            mounts_advanced_mode=mounts_advanced_mode,
            env_vars_advanced_acknowledged=env_vars_advanced_acknowledged,
            mounts_advanced_acknowledged=mounts_advanced_acknowledged,
            ports=ports,
            ports_unlocked=ports_unlocked,
            ports_advanced_acknowledged=ports_advanced_acknowledged,
            gh_management_locked=gh_locked,
            workspace_type=workspace_type,
            workspace_target=workspace_target,
            gh_use_host_cli=gh_use_host_cli,
            gh_context_enabled=gh_context_enabled,
            github_polling_enabled=github_polling_enabled,
            agentsnova_trusted_users_env=agentsnova_trusted_users_env,
            agentsnova_trusted_mode=agentsnova_trusted_mode,
            prompts=prompts,
            prompts_unlocked=prompts_unlocked,
            agent_selection=agent_selection,
            use_cross_agents=use_cross_agents,
            cross_agent_allowlist=cross_agent_allowlist,
        )

    def _on_test_preflight(self) -> None:
        env = self._draft_environment_from_form()
        if env is None:
            return
        self.test_preflight_requested.emit(env)
