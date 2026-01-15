from __future__ import annotations

import os

from dataclasses import replace
from uuid import uuid4

from PySide6.QtWidgets import QFileDialog
from PySide6.QtWidgets import QInputDialog
from PySide6.QtWidgets import QMessageBox

from agents_runner.environments import ALLOWED_STAINS
from agents_runner.environments import Environment
from agents_runner.environments import WORKSPACE_CLONED
from agents_runner.environments import WORKSPACE_MOUNTED
from agents_runner.environments import WORKSPACE_NONE
from agents_runner.environments import delete_environment
from agents_runner.environments import load_environments
from agents_runner.environments import parse_env_vars_text
from agents_runner.environments import parse_mounts_text
from agents_runner.environments import save_environment
from agents_runner.gh_management import is_gh_available
from agents_runner.ui.dialogs.new_environment_wizard import NewEnvironmentWizard


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
        wizard.environment_created.connect(
            lambda env: self.updated.emit(env.env_id)
        )
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

    def _on_save(self) -> None:
        self.try_autosave()

    def try_autosave(self, *, preferred_env_id: str | None = None) -> bool:
        env_id = self._current_env_id
        if not env_id:
            return True
        name = (self._name.text() or "").strip()
        if not name:
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
        workspace_type = existing.workspace_type or WORKSPACE_NONE if existing else WORKSPACE_NONE
        workspace_target = str(existing.workspace_target or "").strip() if existing else ""
        gh_locked = True
        gh_use_host_cli = (
            bool(getattr(existing, "gh_use_host_cli", True)) if existing else False
        )
        gh_context_enabled = (
            bool(getattr(existing, "gh_context_enabled", False))
            if existing
            else False
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

        env_vars, errors = parse_env_vars_text(self._env_vars.toPlainText() or "")
        if errors:
            QMessageBox.warning(
                self, "Invalid env vars", "Fix env vars:\n" + "\n".join(errors[:12])
            )
            return False

        mounts = parse_mounts_text(self._mounts.toPlainText() or "")
        prompts, prompts_unlocked = self._prompts_tab.get_prompts()
        agent_selection = self._agents_tab.get_agent_selection()

        # Read preflight scripts based on container caching state
        container_caching_enabled = bool(self._container_caching_enabled.isChecked())
        
        if container_caching_enabled:
            # Dual-editor mode: read from both editors
            cached_preflight_script = (
                str(self._cached_preflight_script.toPlainText() or "")
                if self._cached_preflight_enabled.isChecked()
                else ""
            )
            preflight_enabled = bool(self._run_preflight_enabled.isChecked())
            preflight_script = str(self._run_preflight_script.toPlainText() or "")
        else:
            # Single-editor mode: read from single editor only
            cached_preflight_script = ""
            preflight_enabled = bool(self._preflight_enabled.isChecked())
            preflight_script = str(self._preflight_script.toPlainText() or "")

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
                cached_preflight_script=cached_preflight_script,
                preflight_enabled=preflight_enabled,
                preflight_script=preflight_script,
                env_vars=env_vars,
                extra_mounts=mounts,
                gh_management_locked=gh_locked,
                workspace_type=workspace_type,
                workspace_target=workspace_target,
                gh_use_host_cli=gh_use_host_cli,
                gh_context_enabled=gh_context_enabled,
                prompts=prompts,
                prompts_unlocked=prompts_unlocked,
                agent_selection=agent_selection,
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
                cached_preflight_script=cached_preflight_script,
                preflight_enabled=preflight_enabled,
                preflight_script=preflight_script,
                env_vars=env_vars,
                extra_mounts=mounts,
                gh_management_locked=gh_locked,
                workspace_type=workspace_type,
                workspace_target=workspace_target,
                gh_use_host_cli=gh_use_host_cli,
                gh_context_enabled=gh_context_enabled,
                prompts=prompts,
                prompts_unlocked=prompts_unlocked,
                agent_selection=agent_selection,
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
        workspace_type = existing.workspace_type or WORKSPACE_NONE if existing else WORKSPACE_NONE
        workspace_target = str(existing.workspace_target or "").strip() if existing else ""
        gh_locked = True
        gh_use_host_cli = (
            bool(getattr(existing, "gh_use_host_cli", True)) if existing else False
        )
        gh_context_enabled = (
            bool(getattr(existing, "gh_context_enabled", False))
            if existing
            else False
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

        env_vars, errors = parse_env_vars_text(self._env_vars.toPlainText() or "")
        if errors:
            QMessageBox.warning(
                self, "Invalid env vars", "Fix env vars:\n" + "\n".join(errors[:12])
            )
            return None

        mounts = parse_mounts_text(self._mounts.toPlainText() or "")
        name = (self._name.text() or "").strip() or env_id
        prompts, prompts_unlocked = self._prompts_tab.get_prompts()
        agent_selection = self._agents_tab.get_agent_selection()

        # Read preflight scripts based on container caching state
        container_caching_enabled = bool(self._container_caching_enabled.isChecked())
        
        if container_caching_enabled:
            # Dual-editor mode: read from both editors
            cached_preflight_script = (
                str(self._cached_preflight_script.toPlainText() or "")
                if self._cached_preflight_enabled.isChecked()
                else ""
            )
            preflight_enabled = bool(self._run_preflight_enabled.isChecked())
            preflight_script = str(self._run_preflight_script.toPlainText() or "")
        else:
            # Single-editor mode: read from single editor only
            cached_preflight_script = ""
            preflight_enabled = bool(self._preflight_enabled.isChecked())
            preflight_script = str(self._preflight_script.toPlainText() or "")

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
                cached_preflight_script=cached_preflight_script,
                preflight_enabled=preflight_enabled,
                preflight_script=preflight_script,
                env_vars=env_vars,
                extra_mounts=mounts,
                gh_management_locked=gh_locked,
                workspace_type=workspace_type,
                workspace_target=workspace_target,
                gh_use_host_cli=gh_use_host_cli,
                gh_context_enabled=gh_context_enabled,
                prompts=prompts,
                prompts_unlocked=prompts_unlocked,
                agent_selection=agent_selection,
            )

        return replace(
            existing,
            name=name,
            color=str(self._color.currentData() or "slate"),
            max_agents_running=max_agents_running,
            headless_desktop_enabled=bool(
                self._headless_desktop_enabled.isChecked()
            ),
            cache_desktop_build=bool(self._cache_desktop_build.isChecked()),
            container_caching_enabled=bool(self._container_caching_enabled.isChecked()),
            cached_preflight_script=cached_preflight_script,
            preflight_enabled=preflight_enabled,
            preflight_script=preflight_script,
            env_vars=env_vars,
            extra_mounts=mounts,
            gh_management_locked=gh_locked,
            workspace_type=workspace_type,
            workspace_target=workspace_target,
            gh_use_host_cli=gh_use_host_cli,
            gh_context_enabled=gh_context_enabled,
            prompts=prompts,
            prompts_unlocked=prompts_unlocked,
            agent_selection=agent_selection,
        )

    def _on_test_preflight(self) -> None:
        env = self._draft_environment_from_form()
        if env is None:
            return
        self.test_preflight_requested.emit(env)
