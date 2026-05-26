from __future__ import annotations

import os
import threading
import time

from datetime import datetime
from datetime import timezone

from PySide6.QtWidgets import QApplication
from PySide6.QtWidgets import QMessageBox

from agents_runner.agent_display import format_agent_markdown_link
from agents_runner.agent_display import get_agent_display_name
from agents_runner.environments import WORKSPACE_CLONED
from agents_runner.environments.model import INTERACTIVE_PR_NO_PROMPT_MODE_MANUAL_REVIEW
from agents_runner.environments.model import normalize_interactive_pr_no_prompt_mode
from agents_runner.gh.git_ops import git_remote_url
from agents_runner.gh.permissions import check_pr_creation_capability_for_repo_ref
from agents_runner.gh_management import commit_push_and_pr
from agents_runner.gh_management import GhManagementError
from agents_runner.log_format import format_log
from agents_runner.pr_metadata import load_pr_metadata
from agents_runner.pr_metadata import normalize_pr_title
from agents_runner.pr_metadata import pr_metadata_host_path
from agents_runner.ui.task_git_metadata import derive_task_git_metadata
from agents_runner.ui.utils import stain_color


class MainWindowTasksInteractiveFinalizeMixin:
    def _on_interactive_finished(self, task_id: str, exit_code: int) -> None:
        task_id = str(task_id or "").strip()
        watch = self._interactive_watch.pop(task_id, None)
        if watch is not None:
            _, stop = watch
            stop.set()

        task = self._tasks.get(task_id)
        if task is None:
            return

        self.host_log.emit(
            task_id,
            format_log(
                "host",
                "interactive",
                "INFO",
                f"Task {task_id}: interactive run finished (exit_code={exit_code}, state={task.status})",
            ),
        )

        try:
            task.exit_code = int(exit_code)
        except Exception:
            task.exit_code = 1
        task.finished_at = datetime.now(tz=timezone.utc)
        task.status = "done" if (task.exit_code or 0) == 0 else "failed"
        task.git = derive_task_git_metadata(task)

        # Validate git metadata for cloned repo tasks
        if task.requires_git_metadata():
            from agents_runner.ui.task_git_metadata import validate_git_metadata

            is_valid, error_msg = validate_git_metadata(task.git)
            if not is_valid:
                self._on_task_log(
                    task_id,
                    format_log(
                        "host",
                        "metadata",
                        "WARN",
                        f"git metadata validation failed: {error_msg}",
                    ),
                )

        env = self._environments.get(task.environment_id)
        stain = env.color if env else None
        spinner = stain_color(env.color) if env else None
        self._dashboard.upsert_task(task, stain=stain, spinner_color=spinner)
        self._details.update_task(task)
        self._schedule_save()
        self._refresh_new_task_agent_info()
        QApplication.beep()
        self._on_task_log(
            task_id,
            format_log("host", "interactive", "INFO", f"exited with {task.exit_code}"),
        )

        # Collect staged artifacts and emit UUIDs back through host_artifacts.
        self._start_artifact_finalization(task)

        # Interactive tasks can create PRs immediately based on environment settings,
        # then mark finalization done. Agent tasks still finalize in background workers.
        if (
            task.status == "done"
            and task.workspace_type == WORKSPACE_CLONED
            and task.gh_repo_root
            and task.gh_branch
            and str(task.gh_branch or "").strip()
            != str(task.gh_base_branch or "").strip()
            and not task.gh_pr_url
            and not str(getattr(task, "gh_pr_unavailable_reason", "") or "").strip()
        ):
            base = str(task.gh_base_branch or "").strip()
            base_display = base or "auto"
            prompt_enabled = bool(
                getattr(env, "interactive_pr_prompt_enabled", True) if env else True
            )
            no_prompt_mode = normalize_interactive_pr_no_prompt_mode(
                getattr(env, "interactive_pr_no_prompt_mode", "auto_create_pr")
                if env
                else "auto_create_pr"
            )

            def _queue_interactive_pr_creation() -> None:
                threading.Thread(
                    target=self._finalize_gh_management_worker,
                    args=(
                        task_id,
                        str(task.gh_repo_root or "").strip(),
                        str(task.gh_branch or "").strip(),
                        str(base).strip(),
                        str(task.prompt or ""),
                        str(task.task_id or task_id),
                        bool(task.gh_use_host_cli),
                        (str(task.gh_pr_metadata_path or "").strip() or None),
                        str(task.agent_cli or "").strip(),
                        str(task.agent_cli_args or "").strip(),
                    ),
                    daemon=True,
                ).start()

            if prompt_enabled:
                message = (
                    "Interactive run finished.\n\n"
                    f"Create a PR from {task.gh_branch} -> {base_display}?"
                )
                if (
                    QMessageBox.question(self, "Create pull request?", message)
                    == QMessageBox.StandardButton.Yes
                ):
                    self.host_log.emit(
                        task_id,
                        format_log(
                            "host",
                            "interactive",
                            "INFO",
                            f"Task {task_id}: creating PR after interactive run (branch={task.gh_branch}, base={base_display})",
                        ),
                    )
                    _queue_interactive_pr_creation()
                else:
                    self.host_log.emit(
                        task_id,
                        format_log(
                            "host",
                            "interactive",
                            "INFO",
                            f"Task {task_id}: PR creation declined by user",
                        ),
                    )
            elif no_prompt_mode == INTERACTIVE_PR_NO_PROMPT_MODE_MANUAL_REVIEW:
                self.host_log.emit(
                    task_id,
                    format_log(
                        "host",
                        "interactive",
                        "INFO",
                        "Interactive PR prompt disabled and mode=manual; use Review -> Create PR to open the PR.",
                    ),
                )
            else:
                self.host_log.emit(
                    task_id,
                    format_log(
                        "host",
                        "interactive",
                        "INFO",
                        f"Interactive PR prompt disabled and mode=auto-create; creating PR ({task.gh_branch} -> {base_display}).",
                    ),
                )
                _queue_interactive_pr_creation()
        elif str(getattr(task, "gh_pr_unavailable_reason", "") or "").strip():
            self.host_log.emit(
                task_id,
                format_log(
                    "gh",
                    "pr",
                    "INFO",
                    (
                        "Interactive PR creation skipped: "
                        f"{task.gh_pr_unavailable_reason}"
                    ),
                ),
            )

        # Mark finalization done for interactive tasks (PR handling selected above).
        self.host_log.emit(
            task_id,
            format_log(
                "host",
                "interactive",
                "INFO",
                f"Task {task_id}: state transition (state=None→done, reason=interactive_finished)",
            ),
        )
        task.finalization_state = "done"
        task.finalization_error = ""
        self._schedule_save()

    def _resolve_pr_metadata_path_for_finalize(
        self,
        *,
        task_id: str,
        provided_path: str | None,
    ) -> str | None:
        normalized_provided = os.path.abspath(
            os.path.expanduser(str(provided_path or "").strip())
        )
        if normalized_provided:
            if os.path.exists(normalized_provided):
                return normalized_provided
            self.host_log.emit(
                task_id,
                format_log(
                    "gh",
                    "pr",
                    "WARN",
                    f"configured PR metadata file is missing: {normalized_provided}",
                ),
            )

        state_path = str(getattr(self, "_state_path", "") or "").strip()
        if not state_path:
            self.host_log.emit(
                task_id,
                format_log(
                    "gh",
                    "pr",
                    "WARN",
                    "state path unavailable; cannot resolve PR metadata fallback path",
                ),
            )
            return None

        fallback_path = os.path.abspath(
            os.path.expanduser(
                pr_metadata_host_path(os.path.dirname(state_path), task_id)
            )
        )
        if os.path.exists(fallback_path):
            if fallback_path != normalized_provided:
                self.host_log.emit(
                    task_id,
                    format_log(
                        "gh",
                        "pr",
                        "INFO",
                        f"using fallback PR metadata file: {fallback_path}",
                    ),
                )
            return fallback_path

        self.host_log.emit(
            task_id,
            format_log(
                "gh",
                "pr",
                "INFO",
                f"no PR metadata file found (checked: {fallback_path}); using generated PR title/body defaults",
            ),
        )
        return None

    def _finalize_gh_management_worker(
        self,
        task_id: str,
        repo_root: str,
        branch: str,
        base_branch: str,
        prompt_text: str,
        task_token: str,
        use_gh: bool,
        pr_metadata_path: str | None = None,
        agent_cli: str = "",
        agent_cli_args: str = "",
        is_override: bool = False,
    ) -> None:
        if not repo_root or not branch:
            return

        start_s = time.monotonic()

        task = self._tasks.get(task_id)

        try:
            # Step 1: Pre-flight validation
            self.host_log.emit(
                task_id,
                format_log("gh", "pr", "INFO", "[1/6] Validating repository..."),
            )

            from agents_runner.gh.pr_validation import check_existing_pr
            from agents_runner.gh.pr_validation import validate_pr_prerequisites

            checks = validate_pr_prerequisites(
                repo_root=repo_root,
                branch=branch,
                use_gh=use_gh,
            )

            # Check for failures
            failed_checks = [(name, msg) for name, passed, msg in checks if not passed]
            if failed_checks:
                for name, msg in failed_checks:
                    self.host_log.emit(
                        task_id,
                        format_log(
                            "gh", "pr", "ERROR", f"validation failed: {name}: {msg}"
                        ),
                    )
                if task and any(name == "gh_cli" for name, _msg in failed_checks):
                    task.gh_pr_unavailable_status = "unavailable"
                    task.gh_pr_unavailable_reason = "; ".join(
                        msg for name, msg in failed_checks if name == "gh_cli"
                    )
                    self._schedule_save()
                return

            existing_skip_reason = (
                str(getattr(task, "gh_pr_unavailable_reason", "") or "").strip()
                if task
                else ""
            )
            if existing_skip_reason:
                self.host_log.emit(
                    task_id,
                    format_log(
                        "gh",
                        "pr",
                        "INFO",
                        f"[2/6] PR creation skipped: {existing_skip_reason}",
                    ),
                )
                return

            # Check for existing PR (informational)
            existing_pr = check_existing_pr(repo_root, branch)
            if existing_pr:
                self.host_log.emit(
                    task_id,
                    format_log(
                        "gh",
                        "pr",
                        "INFO",
                        f"[2/6] Pull request already exists: {existing_pr}",
                    ),
                )
                self.host_pr_url.emit(task_id, existing_pr)
                if task:
                    task.gh_pr_url = existing_pr
                    self._schedule_save()
                return

            self.host_log.emit(
                task_id,
                format_log(
                    "gh", "pr", "INFO", "[2/6] No existing PR found, proceeding..."
                ),
            )

            remote_url = git_remote_url(repo_root) or ""
            capability = check_pr_creation_capability_for_repo_ref(
                remote_url,
                use_gh=bool(use_gh),
            )
            if not capability.can_create_pr:
                self.host_log.emit(
                    task_id,
                    format_log(
                        "gh",
                        "pr",
                        "WARN",
                        f"[3/6] PR creation unavailable: {capability.reason}",
                    ),
                )
                if task:
                    task.gh_pr_unavailable_status = capability.status
                    task.gh_pr_unavailable_reason = capability.reason
                    self._schedule_save()
                return

            self.host_log.emit(
                task_id,
                format_log("gh", "pr", "INFO", "[3/6] Preparing PR metadata..."),
            )

            prompt_line = (
                (prompt_text or "").strip().splitlines()[0] if prompt_text else ""
            )
            default_title = f"Agent Runner: {prompt_line or task_id}"
            default_title = normalize_pr_title(default_title, fallback=default_title)

            agent_display = get_agent_display_name(agent_cli) if agent_cli else "Agent"
            agent_link = (
                format_agent_markdown_link(agent_cli) if agent_cli else agent_display
            )
            runners_link = (
                "[Agents Runner](https://github.com/Midori-AI-OSS/Agents-Runner)"
            )

            default_body = (
                f"Automated by {runners_link}.\n\n"
                f"Agent: {agent_link}\n\n"
                f"Task: {task_token}\n\n"
                "Prompt:\n"
                f"{(prompt_text or '').strip()}\n"
            )
            provided_metadata_path = (
                str(pr_metadata_path or "").strip()
                or (
                    str(getattr(task, "gh_pr_metadata_path", "") or "").strip()
                    if task
                    else ""
                )
                or None
            )
            resolved_pr_metadata_path = self._resolve_pr_metadata_path_for_finalize(
                task_id=task_id,
                provided_path=provided_metadata_path,
            )
            metadata = (
                load_pr_metadata(resolved_pr_metadata_path)
                if resolved_pr_metadata_path
                else None
            )
            if metadata is not None and (metadata.title or metadata.body):
                self.host_log.emit(
                    task_id,
                    format_log(
                        "gh",
                        "pr",
                        "INFO",
                        f"using PR metadata from {resolved_pr_metadata_path}",
                    ),
                )
            elif resolved_pr_metadata_path:
                self.host_log.emit(
                    task_id,
                    format_log(
                        "gh",
                        "pr",
                        "INFO",
                        f"PR metadata file is empty: {resolved_pr_metadata_path}; using generated defaults where needed",
                    ),
                )
            title = (
                normalize_pr_title(str(metadata.title or ""), fallback=default_title)
                if metadata is not None
                else default_title
            )
            body = str(metadata.body or "").strip() if metadata is not None else ""
            if not body:
                body = default_body

            # Add override note for non-cloned-repo modes
            if is_override:
                body += "\n\n---\n**Note:** This is an override PR created manually for a cloned repo environment."

            self.host_log.emit(
                task_id,
                format_log(
                    "gh",
                    "pr",
                    "INFO",
                    f"[4/6] Creating PR from {branch} -> {base_branch or 'auto'}",
                ),
            )
            try:
                pr_url = commit_push_and_pr(
                    repo_root,
                    branch=branch,
                    base_branch=base_branch,
                    title=title,
                    body=body,
                    use_gh=bool(use_gh),
                    agent_cli=agent_cli,
                    agent_cli_args=agent_cli_args,
                )
            except GhManagementError as exc:
                self.host_log.emit(
                    task_id, format_log("gh", "pr", "ERROR", f"failed: {exc}")
                )
                return
            except Exception as exc:
                self.host_log.emit(
                    task_id, format_log("gh", "pr", "ERROR", f"failed: {exc}")
                )
                return

            if pr_url is None:
                self.host_log.emit(
                    task_id,
                    format_log(
                        "gh", "pr", "INFO", "[5/6] No changes to commit; skipping PR"
                    ),
                )
                return
            if pr_url == "":
                self.host_log.emit(
                    task_id,
                    format_log(
                        "gh",
                        "pr",
                        "INFO",
                        "[5/6] Branch pushed; PR creation skipped (gh disabled or missing)",
                    ),
                )
                return
            self.host_log.emit(
                task_id,
                format_log(
                    "gh", "pr", "INFO", f"[6/6] PR created successfully: {pr_url}"
                ),
            )
            self.host_pr_url.emit(task_id, pr_url)

            # Update task PR URL
            if task:
                task.gh_pr_url = pr_url
                self._schedule_save()
        finally:
            elapsed_s = time.monotonic() - start_s
            self.host_log.emit(
                task_id,
                format_log(
                    "host",
                    "finalize",
                    "INFO",
                    f"PR preparation finished in {elapsed_s:.1f}s",
                ),
            )
