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
from agents_runner.environments import delete_environment
from agents_runner.environments import normalize_gh_management_mode
from agents_runner.environments import parse_env_vars_text
from agents_runner.environments import parse_mounts_text
from agents_runner.environments import save_environment
from agents_runner.gh_management import is_gh_available


class _EnvironmentsPageActionsMixin:
    def _sync_gh_management_controls(self, *_: object, env: Environment | None = None) -> None:
        if env is None:
            env = self._environments.get(str(self._current_env_id or ""))

        gh_available = bool(is_gh_available())
        mode = normalize_gh_management_mode(str(self._gh_management_mode.currentData() or GH_MANAGEMENT_NONE))
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
        name, ok = QInputDialog.getText(self, "New environment", "Name")
        if not ok:
            return
        name = (name or "").strip() or "New environment"

        base = self._environments.get(str(self._env_select.currentData() or ""))
        env_id = f"env-{uuid4().hex[:8]}"
        color = "emerald"
        if base and base.color in ALLOWED_STAINS:
            idx = ALLOWED_STAINS.index(base.color)
            color = ALLOWED_STAINS[(idx + 1) % len(ALLOWED_STAINS)]

        workspace_labels = ["Lock to local folder", "Lock to GitHub repo (clone)"]
        selected_label, ok = QInputDialog.getItem(
            self,
            "Workspace",
            "Workspace type",
            workspace_labels,
            0,
            False,
        )
        if not ok:
            return

        gh_management_mode = GH_MANAGEMENT_LOCAL
        gh_management_target = ""
        gh_pr_metadata_enabled = False
        if selected_label == "Lock to GitHub repo (clone)":
            repo, ok = QInputDialog.getText(self, "GitHub repo", "Repo (owner/repo or URL)")
            if not ok:
                return
            repo = (repo or "").strip()
            if not repo:
                QMessageBox.warning(self, "Missing repo", "Enter a GitHub repo like owner/repo (or a URL).")
                return
            gh_management_mode = GH_MANAGEMENT_GITHUB
            gh_management_target = repo
            gh_pr_metadata_enabled = (
                QMessageBox.question(
                    self,
                    "PR metadata",
                    "Allow the agent to set the PR title/body via a mounted JSON file?\n\n"
                    "This is only used for non-interactive runs.",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No,
                )
                == QMessageBox.Yes
            )
        else:
            folder = QFileDialog.getExistingDirectory(self, "Select workspace folder", os.getcwd())
            if not folder:
                return
            gh_management_target = folder

        gh_use_host_cli = bool(getattr(base, "gh_use_host_cli", True)) if base else True
        if not is_gh_available():
            gh_use_host_cli = False
        try:
            max_agents_running = int(str(getattr(base, "max_agents_running", -1) if base else -1).strip())
        except Exception:
            max_agents_running = -1
        env = Environment(
            env_id=env_id,
            name=name,
            color=color,
            host_workdir="",
            host_codex_dir=base.host_codex_dir if base else "",
            agent_cli_args=base.agent_cli_args if base else "",
            max_agents_running=max_agents_running,
            preflight_enabled=base.preflight_enabled if base else False,
            preflight_script=base.preflight_script if base else "",
            env_vars=dict(base.env_vars) if base else {},
            extra_mounts=list(base.extra_mounts) if base else [],
            gh_management_mode=gh_management_mode,
            gh_management_target=gh_management_target,
            gh_management_locked=True,
            gh_use_host_cli=gh_use_host_cli,
            gh_pr_metadata_enabled=bool(gh_pr_metadata_enabled),
            prompts=[],
            prompts_unlocked=False,
            agent_selection=None,
        )
        save_environment(env)
        self.updated.emit(env_id)

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

    def try_autosave(self) -> bool:
        env_id = self._current_env_id
        if not env_id:
            return True
        name = (self._name.text() or "").strip()
        if not name:
            QMessageBox.warning(self, "Missing name", "Enter an environment name first.")
            return False

        existing = self._environments.get(env_id)
        host_codex_dir = os.path.expanduser((self._host_codex_dir.text() or "").strip())
        agent_cli_args = (self._agent_cli_args.text() or "").strip()
        max_agents_text = str(self._max_agents_running.text() or "-1").strip()
        try:
            max_agents_running = int(max_agents_text)
        except ValueError:
            max_agents_running = -1

        gh_mode = normalize_gh_management_mode(existing.gh_management_mode if existing else GH_MANAGEMENT_NONE)
        gh_target = str(existing.gh_management_target or "").strip() if existing else ""
        gh_locked = True
        gh_use_host_cli = bool(getattr(existing, "gh_use_host_cli", True)) if existing else False
        gh_pr_metadata_enabled = bool(getattr(existing, "gh_pr_metadata_enabled", False)) if existing else False

        if existing and gh_mode == GH_MANAGEMENT_GITHUB:
            gh_pr_metadata_enabled = bool(self._gh_pr_metadata_enabled.isChecked())
        elif gh_mode != GH_MANAGEMENT_GITHUB:
            gh_pr_metadata_enabled = False

        env_vars, errors = parse_env_vars_text(self._env_vars.toPlainText() or "")
        if errors:
            QMessageBox.warning(self, "Invalid env vars", "Fix env vars:\n" + "\n".join(errors[:12]))
            return False

        mounts = parse_mounts_text(self._mounts.toPlainText() or "")
        prompts, prompts_unlocked = self._prompts_tab.get_prompts()
        agent_selection = self._agents_tab.get_agent_selection()

        env = Environment(
            env_id=env_id,
            name=name,
            color=str(self._color.currentData() or "slate"),
            host_workdir="",
            host_codex_dir=host_codex_dir,
            agent_cli_args=agent_cli_args,
            max_agents_running=max_agents_running,
            preflight_enabled=bool(self._preflight_enabled.isChecked()),
            preflight_script=str(self._preflight_script.toPlainText() or ""),
            env_vars=env_vars,
            extra_mounts=mounts,
            gh_management_mode=gh_mode,
            gh_management_target=gh_target,
            gh_management_locked=gh_locked,
            gh_use_host_cli=gh_use_host_cli,
            gh_pr_metadata_enabled=gh_pr_metadata_enabled,
            prompts=prompts,
            prompts_unlocked=prompts_unlocked,
            agent_selection=agent_selection,
        )
        save_environment(env)
        self.updated.emit(env_id)
        return True

    def selected_environment_id(self) -> str:
        return str(self._env_select.currentData() or "")

    def _draft_environment_from_form(self) -> Environment | None:
        env_id = self._current_env_id
        if not env_id:
            return None

        existing = self._environments.get(env_id)
        host_codex_dir = os.path.expanduser((self._host_codex_dir.text() or "").strip())
        agent_cli_args = (self._agent_cli_args.text() or "").strip()
        max_agents_text = str(self._max_agents_running.text() or "-1").strip()
        try:
            max_agents_running = int(max_agents_text)
        except ValueError:
            max_agents_running = -1

        gh_mode = normalize_gh_management_mode(existing.gh_management_mode if existing else GH_MANAGEMENT_NONE)
        gh_target = str(existing.gh_management_target or "").strip() if existing else ""
        gh_locked = True
        gh_use_host_cli = bool(getattr(existing, "gh_use_host_cli", True)) if existing else False
        gh_pr_metadata_enabled = bool(getattr(existing, "gh_pr_metadata_enabled", False)) if existing else False

        if existing and gh_mode == GH_MANAGEMENT_GITHUB:
            gh_pr_metadata_enabled = bool(self._gh_pr_metadata_enabled.isChecked())
        elif gh_mode != GH_MANAGEMENT_GITHUB:
            gh_pr_metadata_enabled = False

        env_vars, errors = parse_env_vars_text(self._env_vars.toPlainText() or "")
        if errors:
            QMessageBox.warning(self, "Invalid env vars", "Fix env vars:\n" + "\n".join(errors[:12]))
            return None

        mounts = parse_mounts_text(self._mounts.toPlainText() or "")
        name = (self._name.text() or "").strip() or env_id
        prompts, prompts_unlocked = self._prompts_tab.get_prompts()
        agent_selection = self._agents_tab.get_agent_selection()

        return Environment(
            env_id=env_id,
            name=name,
            color=str(self._color.currentData() or "slate"),
            host_workdir="",
            host_codex_dir=host_codex_dir,
            agent_cli_args=agent_cli_args,
            max_agents_running=max_agents_running,
            preflight_enabled=bool(self._preflight_enabled.isChecked()),
            preflight_script=str(self._preflight_script.toPlainText() or ""),
            env_vars=env_vars,
            extra_mounts=mounts,
            gh_management_mode=gh_mode,
            gh_management_target=gh_target,
            gh_management_locked=gh_locked,
            gh_use_host_cli=gh_use_host_cli,
            gh_pr_metadata_enabled=gh_pr_metadata_enabled,
            prompts=prompts,
            prompts_unlocked=prompts_unlocked,
            agent_selection=agent_selection,
        )

    def _on_test_preflight(self) -> None:
        env = self._draft_environment_from_form()
        if env is None:
            return
        self.test_preflight_requested.emit(env)

