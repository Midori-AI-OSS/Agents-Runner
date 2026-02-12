from __future__ import annotations

import re
from dataclasses import dataclass

from agents_runner.environments.git_operations import get_git_info
from agents_runner.gh.git_ops import parse_github_url

from .model import Environment
from .model import WORKSPACE_CLONED
from .model import WORKSPACE_MOUNTED


@dataclass(frozen=True)
class GitHubRepoContext:
    repo_owner: str
    repo_name: str
    repo_url: str
    source: str

    @property
    def repo_full_name(self) -> str:
        return f"{self.repo_owner}/{self.repo_name}"


def _parse_cloned_target(target: str) -> tuple[str | None, str | None]:
    value = str(target or "").strip()
    if not value:
        return (None, None)

    shorthand = re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", value)
    if shorthand:
        owner, repo = value.split("/", 1)
        return (owner.strip(), repo.strip())

    return parse_github_url(value)


def resolve_environment_github_repo(
    env: Environment | None,
) -> GitHubRepoContext | None:
    if env is None:
        return None

    workspace_type = str(getattr(env, "workspace_type", "") or "").strip().lower()

    if workspace_type == WORKSPACE_CLONED:
        owner, repo = _parse_cloned_target(str(getattr(env, "workspace_target", "")))
        if not owner or not repo:
            return None
        return GitHubRepoContext(
            repo_owner=owner,
            repo_name=repo,
            repo_url=f"https://github.com/{owner}/{repo}",
            source="cloned",
        )

    if workspace_type == WORKSPACE_MOUNTED:
        folder = str(getattr(env, "workspace_target", "") or "").strip()
        if not folder:
            return None
        git_info = get_git_info(folder)
        if git_info is None:
            return None
        owner = str(git_info.repo_owner or "").strip()
        repo = str(git_info.repo_name or "").strip()
        if not owner or not repo:
            return None
        repo_url = str(git_info.repo_url or "").strip() or (
            f"https://github.com/{owner}/{repo}"
        )
        return GitHubRepoContext(
            repo_owner=owner,
            repo_name=repo,
            repo_url=repo_url,
            source="mounted",
        )

    return None
