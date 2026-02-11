"""GitHub repository operations for agent worker."""

from typing import Callable

from agents_runner.docker.config import DockerRunnerConfig
from agents_runner.gh_management import GhManagementError
from agents_runner.gh_management import prepare_github_repo_for_task
from agents_runner.log_format import format_log


class GitHubOperations:
    """Handles GitHub repository preparation for agent tasks."""

    @staticmethod
    def prepare_github_repo(
        config: DockerRunnerConfig,
        on_log: Callable[[str], None],
        on_done: Callable[[int, str | None, list[str]], None],
    ) -> tuple[str | None, str | None, str | None]:
        """Prepare GitHub repository for the task.

        Returns:
            Tuple of (repo_root, base_branch, task_branch)

        Raises:
            Returns early via on_done callback if preparation fails critically.
        """
        gh_repo_root: str | None = None
        gh_base_branch: str | None = None
        gh_branch: str | None = None

        if not config.gh_repo:
            return (None, None, None)

        try:
            result = prepare_github_repo_for_task(
                config.gh_repo,
                config.host_workdir,
                task_id=config.task_id,
                base_branch=config.gh_base_branch or None,
                prefer_gh=config.gh_prefer_gh_cli,
                recreate_if_needed=config.gh_recreate_if_needed,
                on_log=on_log,
            )
            gh_repo_root = str(result.get("repo_root") or "") or None
            gh_base_branch = str(result.get("base_branch") or "") or None
            gh_branch = str(result.get("branch") or "") or None

            if gh_branch:
                on_log(
                    format_log(
                        "gh",
                        "repo",
                        "INFO",
                        f"ready on branch {gh_branch}",
                    )
                )

            # Update GitHub context file after clone (if context file exists)
            if config.gh_context_file_path and gh_repo_root:
                GitHubOperations._update_github_context(
                    config,
                    gh_repo_root,
                    gh_base_branch,
                    gh_branch,
                    on_log,
                )

        except (GhManagementError, Exception) as exc:
            on_log(format_log("gh", "repo", "ERROR", str(exc)))
            on_log(
                format_log(
                    "gh",
                    "repo",
                    "ERROR",
                    "GitHub setup failed; PR creation will be unavailable for this task",
                )
            )
            on_done(1, str(exc), [])
            raise

        return (gh_repo_root, gh_base_branch, gh_branch)

    @staticmethod
    def _update_github_context(
        config: DockerRunnerConfig,
        gh_repo_root: str,
        gh_base_branch: str | None,
        gh_branch: str | None,
        on_log: Callable[[str], None],
    ) -> None:
        """Update GitHub context file after repository clone."""
        try:
            from agents_runner.environments.git_operations import get_git_info
            from agents_runner.pr_metadata import GitHubContext
            from agents_runner.pr_metadata import update_github_context_after_clone

            git_info = get_git_info(gh_repo_root)
            if git_info:
                github_context = GitHubContext(
                    repo_url=git_info.repo_url,
                    repo_owner=git_info.repo_owner,
                    repo_name=git_info.repo_name,
                    base_branch=gh_base_branch or git_info.branch,
                    task_branch=gh_branch,
                    head_commit=git_info.commit_sha,
                )
                update_github_context_after_clone(
                    config.gh_context_file_path,
                    github_context=github_context,
                )
                on_log(
                    format_log(
                        "gh",
                        "repo",
                        "INFO",
                        "updated GitHub context file",
                    )
                )
            else:
                on_log(
                    format_log(
                        "gh",
                        "repo",
                        "WARN",
                        "Could not detect git repository information",
                    )
                )
                on_log(
                    format_log(
                        "gh",
                        "repo",
                        "WARN",
                        f"Checked path: {gh_repo_root}",
                    )
                )
                on_log(
                    format_log(
                        "gh",
                        "repo",
                        "WARN",
                        "Agent will execute without repository context",
                    )
                )
                on_log(
                    format_log(
                        "gh",
                        "repo",
                        "INFO",
                        "This may affect code quality but PR creation should still work",
                    )
                )
                on_log(
                    format_log(
                        "gh",
                        "repo",
                        "INFO",
                        "TIP: Check repository clone logs above for errors",
                    )
                )
        except Exception as exc:
            on_log(
                format_log(
                    "gh",
                    "repo",
                    "ERROR",
                    f"Failed to update GitHub context: {exc}",
                )
            )
            on_log(
                format_log(
                    "gh",
                    "repo",
                    "ERROR",
                    f"Context file path: {config.gh_context_file_path}",
                )
            )
            on_log(
                format_log(
                    "gh",
                    "repo",
                    "ERROR",
                    f"Repository root: {gh_repo_root}",
                )
            )
            on_log(
                format_log(
                    "gh",
                    "repo",
                    "WARN",
                    "Agent will execute without repository context",
                )
            )
            on_log(
                format_log(
                    "gh",
                    "repo",
                    "INFO",
                    "This may affect code quality but PR creation should still work",
                )
            )
            # Don't fail the task if context update fails
