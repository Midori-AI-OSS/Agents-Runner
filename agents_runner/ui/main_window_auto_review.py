from __future__ import annotations

from PySide6.QtWidgets import QDialog

from agents_runner.environments import WORKSPACE_CLONED
from agents_runner.gh.git_ops import git_list_remote_heads
from agents_runner.ui.dialogs.auto_review_branch_dialog import AutoReviewBranchDialog
from midori_ai_logger import MidoriAiLogger

logger = MidoriAiLogger(channel=None, name=__name__)


class MainWindowAutoReviewMixin:
    def _on_auto_review_requested(self, env_id: str, prompt: str) -> None:
        selected_env_id = str(env_id or "").strip() or self._active_environment_id()
        if not selected_env_id:
            return

        resolved_base_branch = self._resolve_auto_review_base_branch(
            env_id=selected_env_id
        )
        if resolved_base_branch is None:
            return

        host_codex = str(self._settings_data.get("host_codex_dir") or "").strip()
        self._start_task_from_ui(
            prompt, host_codex, selected_env_id, resolved_base_branch
        )

    def _resolve_auto_review_base_branch(self, *, env_id: str) -> str | None:
        env = self._environments.get(str(env_id or "").strip())
        if env is None:
            return ""

        workspace_type = str(getattr(env, "workspace_type", "") or "").strip().lower()
        if workspace_type != WORKSPACE_CLONED:
            return ""

        repo_target = str(getattr(env, "workspace_target", "") or "").strip()
        if not repo_target:
            return ""

        branches = git_list_remote_heads(repo_target)
        if not branches:
            logger.warning(
                (
                    "[github-auto-review] skipped: failed to refresh remote branches "
                    f"for environment '{env_id}' ({repo_target})."
                )
            )
            return None

        branch_lookup = {name.casefold(): name for name in branches}
        saved_branch = str(getattr(env, "gh_last_base_branch", "") or "").strip()
        if saved_branch:
            matched = branch_lookup.get(saved_branch.casefold())
            if matched:
                return matched

            dialog = AutoReviewBranchDialog(
                environment_name=str(getattr(env, "name", "") or env_id),
                previous_branch=saved_branch,
                branches=branches,
                timeout_seconds=15,
                parent=self,
            )
            if dialog.exec() != QDialog.DialogCode.Accepted:
                logger.info(
                    (
                        "[github-auto-review] skipped: branch selector cancelled for "
                        f"environment '{env_id}'."
                    )
                )
                return None

            selected = str(dialog.selected_branch() or "").strip()
            if not selected:
                return ""
            return branch_lookup.get(selected.casefold(), "")

        return ""
