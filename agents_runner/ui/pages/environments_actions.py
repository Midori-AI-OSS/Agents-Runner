from __future__ import annotations

import os

from uuid import uuid4

from PySide6.QtWidgets import QFileDialog
from PySide6.QtWidgets import QInputDialog
from PySide6.QtWidgets import QMessageBox

from agents_runner.environments import ALLOWED_STAINS
from agents_runner.environments import Environment
from agents_runner.environments import GH_MANAGEMENT_GITHUB
from agents_runner.environments import GH_MANAGEMENT_LOCAL
from agents_runner.environments import GH_MANAGEMENT_NONE
from agents_runner.environments import WORKSPACE_CLONED
from agents_runner.environments import WORKSPACE_MOUNTED
from agents_runner.environments import WORKSPACE_NONE
from agents_runner.environments import delete_environment
from agents_runner.environments import normalize_gh_management_mode
from agents_runner.environments import parse_env_vars_text
from agents_runner.environments import parse_mounts_text
from agents_runner.environments import save_environment
from agents_runner.gh_management import is_gh_available
from agents_runner.ui.dialogs.new_environment_wizard import NewEnvironmentWizard


class _EnvironmentsPageActionsMixin:
    def _sync_gh_management_controls(
        self, *_: object, env: Environment | None = None
    ) -> None:
        if env is None:
            env = self._environments.get(str(self._current_env_id or ""))

        gh_available = bool(is_gh_available())
        mode = normalize_gh_management_mode(
            str(self._gh_management_mode.currentData() or GH_MANAGEMENT_NONE)
        )
        locked = env is not None
        if locked and env is not None:
            desired_mode = normalize_gh_management_mode(env.gh_management_mode)
            if desired_mode != mode:
                idx = self._gh_management_mode.findData(desired_mode)
                if idx >= 0:
                    self._gh_management_mode.blockSignals(True)
                    try:
                        self._gh_management_mode.setCurrentIndex(idx)
                    finally:
                        self._gh_management_mode.blockSignals(False)
                mode = desired_mode
            desired_target = str(env.gh_management_target or "")
            if (self._gh_management_target.text() or "") != desired_target:
                self._gh_management_target.blockSignals(True)
                try:
                    self._gh_management_target.setText(desired_target)
                finally:
                    self._gh_management_target.blockSignals(False)
            desired_gh = bool(getattr(env, "gh_use_host_cli", True))
            if bool(self._gh_use_host_cli.isChecked()) != desired_gh:
                self._gh_use_host_cli.blockSignals(True)
                try:
                    self._gh_use_host_cli.setChecked(desired_gh)
                finally:
                    self._gh_use_host_cli.blockSignals(False)

        self._gh_management_mode.setEnabled(not locked)
        self._gh_management_target.setEnabled(not locked)
        self._gh_use_host_cli.setVisible(False)
        self._gh_use_host_cli.setEnabled(not locked and gh_available)
        if not gh_available:
            self._gh_use_host_cli.setChecked(False)

        wants_browse = mode == GH_MANAGEMENT_LOCAL
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
        max_agents_text = str(self._max_agents_running.text() or "-1").strip()
        try:
            max_agents_running = int(max_agents_text)
        except ValueError:
            max_agents_running = -1

        gh_mode = normalize_gh_management_mode(
            existing.gh_management_mode if existing else GH_MANAGEMENT_NONE
        )
        gh_target = str(existing.gh_management_target or "").strip() if existing else ""
        gh_locked = True
        gh_use_host_cli = (
            bool(getattr(existing, "gh_use_host_cli", True)) if existing else False
        )
        gh_context_enabled = (
            bool(getattr(existing, "gh_context_enabled", False))
            if existing
            else False
        )
        
        # Determine workspace_type based on gh_mode
        if gh_mode == GH_MANAGEMENT_GITHUB:
            workspace_type = WORKSPACE_CLONED
        elif gh_mode == GH_MANAGEMENT_LOCAL:
            workspace_type = WORKSPACE_MOUNTED
        else:
            workspace_type = WORKSPACE_NONE

        if existing and gh_mode == GH_MANAGEMENT_GITHUB:
            gh_context_enabled = bool(self._gh_context_enabled.isChecked())
        elif existing and gh_mode == GH_MANAGEMENT_LOCAL:
            # For folder-locked, respect checkbox if git was detected
            is_git_repo = existing.detect_git_if_folder_locked()
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

        env = Environment(
            env_id=env_id,
            name=name,
            color=str(self._color.currentData() or "slate"),
            host_workdir="",
            max_agents_running=max_agents_running,
            headless_desktop_enabled=bool(self._headless_desktop_enabled.isChecked()),
            cache_desktop_build=bool(self._cache_desktop_build.isChecked()),
            container_caching_enabled=bool(self._container_caching_enabled.isChecked()),
            cached_preflight_script=cached_preflight_script,
            preflight_enabled=preflight_enabled,
            preflight_script=preflight_script,
            env_vars=env_vars,
            extra_mounts=mounts,
            gh_management_mode=gh_mode,
            gh_management_target=gh_target,
            gh_management_locked=gh_locked,
            workspace_type=workspace_type,
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

        gh_mode = normalize_gh_management_mode(
            existing.gh_management_mode if existing else GH_MANAGEMENT_NONE
        )
        gh_target = str(existing.gh_management_target or "").strip() if existing else ""
        gh_locked = True
        gh_use_host_cli = (
            bool(getattr(existing, "gh_use_host_cli", True)) if existing else False
        )
        gh_context_enabled = (
            bool(getattr(existing, "gh_context_enabled", False))
            if existing
            else False
        )
        
        # Determine workspace_type based on gh_mode
        if gh_mode == GH_MANAGEMENT_GITHUB:
            workspace_type = WORKSPACE_CLONED
        elif gh_mode == GH_MANAGEMENT_LOCAL:
            workspace_type = WORKSPACE_MOUNTED
        else:
            workspace_type = WORKSPACE_NONE

        if existing and gh_mode == GH_MANAGEMENT_GITHUB:
            gh_context_enabled = bool(self._gh_context_enabled.isChecked())
        elif existing and gh_mode == GH_MANAGEMENT_LOCAL:
            # For folder-locked, respect checkbox if git was detected
            is_git_repo = existing.detect_git_if_folder_locked()
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

        return Environment(
            env_id=env_id,
            name=name,
            color=str(self._color.currentData() or "slate"),
            host_workdir="",
            max_agents_running=max_agents_running,
            headless_desktop_enabled=bool(self._headless_desktop_enabled.isChecked()),
            cache_desktop_build=bool(self._cache_desktop_build.isChecked()),
            container_caching_enabled=bool(self._container_caching_enabled.isChecked()),
            cached_preflight_script=cached_preflight_script,
            preflight_enabled=preflight_enabled,
            preflight_script=preflight_script,
            env_vars=env_vars,
            extra_mounts=mounts,
            gh_management_mode=gh_mode,
            gh_management_target=gh_target,
            gh_management_locked=gh_locked,
            workspace_type=workspace_type,
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
