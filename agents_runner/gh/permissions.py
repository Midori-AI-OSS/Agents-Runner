from __future__ import annotations

import json
import shutil

from dataclasses import dataclass
from typing import Literal
from typing import cast

from .git_ops import parse_github_url
from .process import run_gh

GitHubPrCapabilityStatus = Literal["available", "read_only", "unavailable"]


@dataclass(frozen=True, slots=True)
class GitHubPrCapability:
    status: GitHubPrCapabilityStatus
    can_create_pr: bool
    reason: str
    repo_owner: str = ""
    repo_name: str = ""


def check_pr_creation_capability_for_repo_ref(
    repo_ref: str,
    *,
    use_gh: bool,
    timeout_s: float = 15.0,
) -> GitHubPrCapability:
    owner, name = parse_github_url(repo_ref)
    if not owner or not name:
        return GitHubPrCapability(
            status="unavailable",
            can_create_pr=False,
            reason="could not determine the GitHub repository owner/name",
        )
    return check_pr_creation_capability(
        owner,
        name,
        use_gh=use_gh,
        timeout_s=timeout_s,
    )


def check_pr_creation_capability(
    repo_owner: str,
    repo_name: str,
    *,
    use_gh: bool,
    timeout_s: float = 15.0,
) -> GitHubPrCapability:
    owner = str(repo_owner or "").strip()
    name = str(repo_name or "").strip()
    if not owner or not name:
        return GitHubPrCapability(
            status="unavailable",
            can_create_pr=False,
            reason="could not determine the GitHub repository owner/name",
        )
    if not use_gh:
        return GitHubPrCapability(
            status="unavailable",
            can_create_pr=False,
            reason="GitHub CLI PR creation is disabled for this environment",
            repo_owner=owner,
            repo_name=name,
        )
    if shutil.which("gh") is None:
        return GitHubPrCapability(
            status="unavailable",
            can_create_pr=False,
            reason="GitHub CLI is not available on the host",
            repo_owner=owner,
            repo_name=name,
        )

    repo = f"{owner}/{name}"
    proc = run_gh(
        [
            "gh",
            "api",
            f"repos/{repo}",
            "-H",
            "Accept: application/vnd.github+json",
        ],
        timeout_s=timeout_s,
    )
    if proc.returncode != 0:
        detail = ((proc.stderr or "") or (proc.stdout or "")).strip()
        reason = "could not read GitHub repository permissions"
        if detail:
            reason = f"{reason}: {detail}"
        return GitHubPrCapability(
            status="unavailable",
            can_create_pr=False,
            reason=reason,
            repo_owner=owner,
            repo_name=name,
        )

    try:
        payload = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        return GitHubPrCapability(
            status="unavailable",
            can_create_pr=False,
            reason="could not parse GitHub repository permission response",
            repo_owner=owner,
            repo_name=name,
        )
    if not isinstance(payload, dict):
        return GitHubPrCapability(
            status="unavailable",
            can_create_pr=False,
            reason="GitHub repository permission response was not an object",
            repo_owner=owner,
            repo_name=name,
        )

    payload_dict = cast(dict[object, object], payload)
    permissions_raw = payload_dict.get("permissions")
    permissions = cast(dict[object, object], permissions_raw) if isinstance(permissions_raw, dict) else {}
    can_push = bool(permissions.get("push"))
    if can_push:
        return GitHubPrCapability(
            status="available",
            can_create_pr=True,
            reason="authenticated GitHub account can push to the repository",
            repo_owner=owner,
            repo_name=name,
        )

    return GitHubPrCapability(
        status="read_only",
        can_create_pr=False,
        reason=(
            f"authenticated GitHub account does not have push access to {repo}; automatic PR creation is unavailable"
        ),
        repo_owner=owner,
        repo_name=name,
    )
