from __future__ import annotations

import threading
import time

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from agents_runner.ui._mixin_hints import _MainWindowHints
else:
    _MainWindowHints = object

from PySide6.QtWidgets import QDialog

from agents_runner.agent_display import format_agent_markdown_link
from agents_runner.environments import WORKSPACE_CLONED
from agents_runner.environments.model import (
    AGENTSNOVA_MARKER_COMMENT_MODE_DELETE_AFTER_15S,
    AGENTSNOVA_MARKER_COMMENT_MODE_DISABLED,
)
from agents_runner.gh.git_ops import git_list_remote_heads
from agents_runner.gh.automation_policy import (
    resolve_effective_auto_review_enabled,
    resolve_effective_marker_comment_mode,
)
from agents_runner.gh.work_items import AUTO_REVIEW_MARKER_TOKEN
from agents_runner.gh.work_items import delete_issue_comment
from agents_runner.gh.work_items import post_comment
from agents_runner.gh.work_items import post_comment_with_id
from agents_runner.ui.dialogs.auto_review_branch_dialog import AutoReviewBranchDialog
from midori_ai_logger import MidoriAiLogger

logger = MidoriAiLogger(channel=None, name=__name__)


class MainWindowAutoReviewMixin(_MainWindowHints):
    def _on_auto_review_requested(self, env_id: str, payload: object) -> None:
        payload_dict: dict[str, Any] = payload if isinstance(payload, dict) else {}
        prompt = str(payload_dict.get("prompt") or "").strip()
        if not prompt:
            return

        selected_env_id = str(env_id or "").strip() or self._active_environment_id()
        if not selected_env_id:
            return

        item_type = str(payload_dict.get("item_type") or "").strip().lower()
        is_pr = item_type == "pr"
        repo_owner = str(payload_dict.get("repo_owner") or "").strip()
        repo_name = str(payload_dict.get("repo_name") or "").strip()
        pr_head_ref = str(payload_dict.get("pr_head_ref") or "").strip()
        pr_base_ref = str(payload_dict.get("pr_base_ref") or "").strip()
        pr_head_repo_owner = str(payload_dict.get("pr_head_repo_owner") or "").strip()
        pr_head_repo_name = str(payload_dict.get("pr_head_repo_name") or "").strip()
        pr_is_cross_repo = bool(payload_dict.get("pr_is_cross_repo") or False)

        same_repo = True
        if pr_head_repo_owner and pr_head_repo_name:
            same_repo = (
                pr_head_repo_owner.strip().lower() == repo_owner.strip().lower()
                and pr_head_repo_name.strip().lower() == repo_name.strip().lower()
            )
        is_cross_repo = pr_is_cross_repo or (pr_head_repo_owner and pr_head_repo_name and not same_repo)

        env_for_task = self._environments.get(selected_env_id)
        if not resolve_effective_auto_review_enabled(
            settings=self._settings_data,
            env=env_for_task,
        ):
            return
        resolved_base_branch = ""
        if is_pr and pr_base_ref:
            resolved_base_branch = pr_base_ref
        else:
            resolved_base_branch = self._resolve_auto_review_base_branch(env_id=selected_env_id)
            if resolved_base_branch is None:
                return
        _agent_cli, host_config_dir, _ = self._effective_agent_and_config(env=env_for_task)
        pr_context: dict[str, object] | None = None
        if is_pr:
            pr_context = {
                "repo_owner": repo_owner,
                "repo_name": repo_name,
                "pr_head_ref": pr_head_ref,
                "pr_base_ref": pr_base_ref,
                "pr_head_repo_owner": pr_head_repo_owner,
                "pr_head_repo_name": pr_head_repo_name,
                "pr_is_cross_repo": is_cross_repo,
            }
        task_id = self._start_task_from_ui(
            prompt,
            host_config_dir,
            selected_env_id,
            resolved_base_branch,
            pr_context,
            None,
        )
        if not task_id:
            return

        if is_pr and is_cross_repo:
            self._post_fork_notice_comment(payload=payload_dict)

        marker_mode = resolve_effective_marker_comment_mode(
            settings=self._settings_data,
            env=env_for_task,
        )
        if marker_mode == AGENTSNOVA_MARKER_COMMENT_MODE_DISABLED:
            return

        comment_id = self._post_auto_review_marker_comment(
            payload=payload_dict,
            task_id=task_id,
        )
        if comment_id is not None and marker_mode == AGENTSNOVA_MARKER_COMMENT_MODE_DELETE_AFTER_15S:
            self._schedule_auto_review_marker_cleanup(
                repo_owner=str(payload_dict.get("repo_owner") or "").strip(),
                repo_name=str(payload_dict.get("repo_name") or "").strip(),
                item_type=item_type,
                number=payload_dict.get("number"),
                comment_id=comment_id,
            )

    def _post_fork_notice_comment(self, *, payload: dict[str, object]) -> None:
        repo_owner = str(payload.get("repo_owner") or "").strip()
        repo_name = str(payload.get("repo_name") or "").strip()
        try:
            number = int(payload.get("number") or 0)
        except Exception:
            number = 0
        pr_head_ref = str(payload.get("pr_head_ref") or "").strip()
        pr_head_repo_owner = str(payload.get("pr_head_repo_owner") or "").strip()
        pr_head_repo_name = str(payload.get("pr_head_repo_name") or "").strip()
        if not repo_owner or not repo_name or number <= 0:
            return

        if not hasattr(self, "_fork_notice_seen"):
            self._fork_notice_seen = set()
        notice_key = (
            f"{repo_owner.lower()}/{repo_name.lower()}#{number}:"
            f"{pr_head_repo_owner.lower()}/{pr_head_repo_name.lower()}:{pr_head_ref}"
        )
        if notice_key in self._fork_notice_seen:
            return
        self._fork_notice_seen.add(notice_key)

        body = "Fork PR detected. Agents Runner cannot auto-checkout fork branches; continuing on the base branch."
        try:
            post_comment(
                repo_owner,
                repo_name,
                item_type="pr",
                number=number,
                body=body,
            )
        except Exception as exc:
            logger.rprint(
                (
                    "[github-auto-review] failed to post fork notice comment for "
                    f"{repo_owner}/{repo_name} PR #{number}: {exc}"
                ),
                mode="warn",
            )

    def _post_auto_review_marker_comment(self, *, payload: dict[str, object], task_id: str) -> int | None:
        repo_owner = str(payload.get("repo_owner") or "").strip()
        repo_name = str(payload.get("repo_name") or "").strip()
        item_type = str(payload.get("item_type") or "").strip().lower()
        item_type = "pr" if item_type == "pr" else "issue"
        try:
            number = int(payload.get("number") or 0)
        except Exception:
            number = 0
        if not repo_owner or not repo_name or number <= 0:
            return

        task = self._tasks.get(str(task_id or "").strip())
        agent_cli = str(getattr(task, "agent_cli", "") or "").strip()
        agent_link = format_agent_markdown_link(agent_cli) if agent_cli else "(unknown)"
        marker_body = (
            f"Agents Runner sees {item_type} #{number}, running agent system to work on this.\n"
            f"Task ID: {task_id}\n"
            f"Agent: {agent_link}\n\n"
            f"{AUTO_REVIEW_MARKER_TOKEN}"
        )

        try:
            return post_comment_with_id(
                repo_owner,
                repo_name,
                item_type=item_type,
                number=number,
                body=marker_body,
            )
        except Exception as exc:
            logger.rprint(
                (
                    "[github-auto-review] failed to post marker comment for "
                    f"{repo_owner}/{repo_name} {item_type} #{number} "
                    f"(task={task_id}): {exc}"
                ),
                mode="warn",
            )
        return None

    def _schedule_auto_review_marker_cleanup(
        self,
        *,
        repo_owner: str,
        repo_name: str,
        item_type: str,
        number: object,
        comment_id: int,
    ) -> None:
        if not repo_owner or not repo_name or int(comment_id or 0) <= 0:
            return

        def _cleanup_worker() -> None:
            time.sleep(15.0)
            try:
                delete_issue_comment(
                    repo_owner,
                    repo_name,
                    comment_id=int(comment_id),
                )
            except Exception as exc:
                logger.rprint(
                    (
                        "[github-auto-review] failed to delete marker comment for "
                        f"{repo_owner}/{repo_name} {item_type} #{number} "
                        f"(comment_id={comment_id}): {exc}"
                    ),
                    mode="warn",
                )

        threading.Thread(target=_cleanup_worker, daemon=True).start()

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
            logger.rprint(
                (
                    "[github-auto-review] skipped: failed to refresh remote branches "
                    f"for environment '{env_id}' ({repo_target})."
                ),
                mode="warn",
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
                logger.rprint(
                    (f"[github-auto-review] skipped: branch selector cancelled for environment '{env_id}'."),
                    mode="info",
                )
                return None

            selected = str(dialog.selected_branch() or "").strip()
            selected_branch = branch_lookup.get(selected.casefold(), "")
            self._remember_environment_base_branch(env, selected_branch)
            return selected_branch

        return ""
