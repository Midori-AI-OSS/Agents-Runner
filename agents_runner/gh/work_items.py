from __future__ import annotations

import json

from dataclasses import dataclass
from typing import Any

from .errors import GhManagementError
from .process import run_gh


@dataclass(frozen=True)
class GitHubReactionSummary:
    thumbs_up: int = 0
    thumbs_down: int = 0
    eyes: int = 0
    rocket: int = 0
    hooray: int = 0


@dataclass(frozen=True)
class GitHubComment:
    comment_id: int
    node_id: str
    body: str
    author: str
    created_at: str
    updated_at: str
    url: str
    reactions: GitHubReactionSummary


@dataclass(frozen=True)
class GitHubWorkItem:
    item_type: str
    number: int
    title: str
    state: str
    url: str
    author: str
    created_at: str
    updated_at: str
    body: str = ""
    is_draft: bool = False


@dataclass(frozen=True)
class GitHubWorkroom:
    item_type: str
    repo_owner: str
    repo_name: str
    number: int
    title: str
    body: str
    state: str
    url: str
    author: str
    created_at: str
    updated_at: str
    is_draft: bool
    comments: list[GitHubComment]


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _safe_text(value: object) -> str:
    return str(value or "").strip()


def run_gh_gh_json(args: list[str], *, timeout_s: float = 45.0) -> object:
    proc = run_gh(["gh", *args], timeout_s=timeout_s)
    if proc.returncode != 0:
        stderr = _safe_text(proc.stderr)
        stdout = _safe_text(proc.stdout)
        extra = stderr or stdout
        if extra:
            raise GhManagementError(f"gh command failed: {' '.join(args)}\n{extra}")
        raise GhManagementError(f"gh command failed: {' '.join(args)}")

    payload = _safe_text(proc.stdout)
    if not payload:
        return {}

    try:
        return json.loads(payload)
    except Exception as exc:
        raise GhManagementError(
            f"failed to parse gh json output for: {' '.join(args)}"
        ) from exc


def run_gh_gh(args: list[str], *, timeout_s: float = 45.0) -> None:
    proc = run_gh(["gh", *args], timeout_s=timeout_s)
    if proc.returncode == 0:
        return
    stderr = _safe_text(proc.stderr)
    stdout = _safe_text(proc.stdout)
    extra = stderr or stdout
    if extra:
        raise GhManagementError(f"gh command failed: {' '.join(args)}\n{extra}")
    raise GhManagementError(f"gh command failed: {' '.join(args)}")


def _parse_reaction_summary(raw: object) -> GitHubReactionSummary:
    if isinstance(raw, dict):
        raw_dict: dict[str, Any] = raw
        return GitHubReactionSummary(
            thumbs_up=max(0, _safe_int(raw_dict.get("+1"))),
            thumbs_down=max(0, _safe_int(raw_dict.get("-1"))),
            eyes=max(0, _safe_int(raw_dict.get("eyes"))),
            rocket=max(0, _safe_int(raw_dict.get("rocket"))),
            hooray=max(0, _safe_int(raw_dict.get("hooray"))),
        )

    groups: list[Any] = raw if isinstance(raw, list) else []
    up = 0
    down = 0
    eyes = 0
    rocket = 0
    hooray = 0
    for item in groups:
        if not isinstance(item, dict):
            continue
        content = _safe_text(item.get("content")).upper()
        total = 0
        users = item.get("users")
        if isinstance(users, dict):
            total = _safe_int(users.get("totalCount"))
        total = max(0, total)
        if content == "THUMBS_UP":
            up = total
        elif content == "THUMBS_DOWN":
            down = total
        elif content == "EYES":
            eyes = total
        elif content == "ROCKET":
            rocket = total
        elif content == "HOORAY":
            hooray = total

    return GitHubReactionSummary(
        thumbs_up=up,
        thumbs_down=down,
        eyes=eyes,
        rocket=rocket,
        hooray=hooray,
    )


def _parse_work_item(item_type: str, raw: object) -> GitHubWorkItem | None:
    if not isinstance(raw, dict):
        return None
    
    raw_dict: dict[str, Any] = raw
    number = _safe_int(raw_dict.get("number"))
    if number <= 0:
        return None

    author = ""
    raw_author = raw_dict.get("author")
    if isinstance(raw_author, dict):
        author = _safe_text(raw_author.get("login"))

    return GitHubWorkItem(
        item_type=item_type,
        number=number,
        title=_safe_text(raw_dict.get("title")) or f"#{number}",
        body=_safe_text(raw_dict.get("body")),
        state=_safe_text(raw_dict.get("state")).lower() or "open",
        url=_safe_text(raw_dict.get("url")),
        author=author,
        created_at=_safe_text(raw_dict.get("createdAt")),
        updated_at=_safe_text(raw_dict.get("updatedAt")),
        is_draft=bool(raw_dict.get("isDraft") or False),
    )


def _repo_full_name(repo_owner: str, repo_name: str) -> str:
    owner = _safe_text(repo_owner)
    name = _safe_text(repo_name)
    if not owner or not name:
        raise GhManagementError("missing repository owner/name")
    return f"{owner}/{name}"


def list_open_pull_requests(
    repo_owner: str,
    repo_name: str,
    *,
    limit: int = 30,
) -> list[GitHubWorkItem]:
    repo = _repo_full_name(repo_owner, repo_name)
    data = run_gh_gh_json(
        [
            "pr",
            "list",
            "--repo",
            repo,
            "--state",
            "open",
            "--limit",
            str(max(1, int(limit))),
            "--json",
            "number,title,body,state,url,author,createdAt,updatedAt,isDraft",
        ],
        timeout_s=45.0,
    )

    rows = data if isinstance(data, list) else []
    items: list[GitHubWorkItem] = []
    for row in rows:
        parsed = _parse_work_item("pr", row)
        if parsed is None:
            continue
        items.append(parsed)
    return items


def list_open_issues(
    repo_owner: str,
    repo_name: str,
    *,
    limit: int = 30,
) -> list[GitHubWorkItem]:
    repo = _repo_full_name(repo_owner, repo_name)
    data = run_gh_gh_json(
        [
            "issue",
            "list",
            "--repo",
            repo,
            "--state",
            "open",
            "--limit",
            str(max(1, int(limit))),
            "--json",
            "number,title,body,state,url,author,createdAt,updatedAt",
        ],
        timeout_s=45.0,
    )

    rows = data if isinstance(data, list) else []
    items: list[GitHubWorkItem] = []
    for row in rows:
        parsed = _parse_work_item("issue", row)
        if parsed is None:
            continue
        items.append(parsed)
    return items


def list_issue_comments(
    repo_owner: str,
    repo_name: str,
    *,
    issue_number: int,
    limit: int = 100,
) -> list[GitHubComment]:
    repo = _repo_full_name(repo_owner, repo_name)
    data = run_gh_gh_json(
        [
            "api",
            f"repos/{repo}/issues/{int(issue_number)}/comments?per_page={max(1, int(limit))}",
            "-H",
            "Accept: application/vnd.github+json",
        ],
        timeout_s=45.0,
    )

    rows = data if isinstance(data, list) else []
    comments: list[GitHubComment] = []
    for row in rows:
        if not isinstance(row, dict):
            continue

        comment_id = _safe_int(row.get("id"))
        if comment_id <= 0:
            continue

        user = row.get("user")
        author = _safe_text(user.get("login") if isinstance(user, dict) else "")

        comments.append(
            GitHubComment(
                comment_id=comment_id,
                node_id=_safe_text(row.get("node_id")),
                body=_safe_text(row.get("body")),
                author=author,
                created_at=_safe_text(row.get("created_at")),
                updated_at=_safe_text(row.get("updated_at")),
                url=_safe_text(row.get("html_url")),
                reactions=_parse_reaction_summary(row.get("reactions")),
            )
        )

    return comments


def get_pull_request_workroom(
    repo_owner: str,
    repo_name: str,
    *,
    number: int,
) -> GitHubWorkroom:
    repo = _repo_full_name(repo_owner, repo_name)
    data = run_gh_gh_json(
        [
            "pr",
            "view",
            str(int(number)),
            "--repo",
            repo,
            "--json",
            "number,title,body,state,url,author,createdAt,updatedAt,isDraft",
        ],
        timeout_s=45.0,
    )
    if not isinstance(data, dict):
        raise GhManagementError("invalid pull request payload")

    author = ""
    raw_author = data.get("author")
    if isinstance(raw_author, dict):
        author = _safe_text(raw_author.get("login"))

    comments = list_issue_comments(
        repo_owner,
        repo_name,
        issue_number=int(number),
        limit=100,
    )

    return GitHubWorkroom(
        item_type="pr",
        repo_owner=_safe_text(repo_owner),
        repo_name=_safe_text(repo_name),
        number=max(1, _safe_int(data.get("number"), int(number))),
        title=_safe_text(data.get("title")) or f"PR #{int(number)}",
        body=_safe_text(data.get("body")),
        state=_safe_text(data.get("state")).lower() or "open",
        url=_safe_text(data.get("url")),
        author=author,
        created_at=_safe_text(data.get("createdAt")),
        updated_at=_safe_text(data.get("updatedAt")),
        is_draft=bool(data.get("isDraft") or False),
        comments=comments,
    )


def get_issue_workroom(
    repo_owner: str,
    repo_name: str,
    *,
    number: int,
) -> GitHubWorkroom:
    repo = _repo_full_name(repo_owner, repo_name)
    data = run_gh_gh_json(
        [
            "issue",
            "view",
            str(int(number)),
            "--repo",
            repo,
            "--json",
            "number,title,body,state,url,author,createdAt,updatedAt",
        ],
        timeout_s=45.0,
    )
    if not isinstance(data, dict):
        raise GhManagementError("invalid issue payload")

    author = ""
    raw_author = data.get("author")
    if isinstance(raw_author, dict):
        author = _safe_text(raw_author.get("login"))

    comments = list_issue_comments(
        repo_owner,
        repo_name,
        issue_number=int(number),
        limit=100,
    )

    return GitHubWorkroom(
        item_type="issue",
        repo_owner=_safe_text(repo_owner),
        repo_name=_safe_text(repo_name),
        number=max(1, _safe_int(data.get("number"), int(number))),
        title=_safe_text(data.get("title")) or f"Issue #{int(number)}",
        body=_safe_text(data.get("body")),
        state=_safe_text(data.get("state")).lower() or "open",
        url=_safe_text(data.get("url")),
        author=author,
        created_at=_safe_text(data.get("createdAt")),
        updated_at=_safe_text(data.get("updatedAt")),
        is_draft=False,
        comments=comments,
    )


def post_comment(
    repo_owner: str,
    repo_name: str,
    *,
    item_type: str,
    number: int,
    body: str,
) -> None:
    repo = _repo_full_name(repo_owner, repo_name)
    text = _safe_text(body)
    if not text:
        raise GhManagementError("comment body is empty")

    normalized = _safe_text(item_type).lower()
    if normalized == "pr":
        run_gh_gh(
            [
                "pr",
                "comment",
                str(int(number)),
                "--repo",
                repo,
                "--body",
                text,
            ],
            timeout_s=45.0,
        )
        return

    if normalized == "issue":
        run_gh_gh(
            [
                "issue",
                "comment",
                str(int(number)),
                "--repo",
                repo,
                "--body",
                text,
            ],
            timeout_s=45.0,
        )
        return

    raise GhManagementError(f"unsupported item type: {item_type}")


def set_item_open_state(
    repo_owner: str,
    repo_name: str,
    *,
    item_type: str,
    number: int,
    open_state: bool,
) -> None:
    repo = _repo_full_name(repo_owner, repo_name)
    normalized = _safe_text(item_type).lower()

    if normalized == "pr":
        subcommand = "reopen" if bool(open_state) else "close"
        run_gh_gh(
            [
                "pr",
                subcommand,
                str(int(number)),
                "--repo",
                repo,
            ],
            timeout_s=45.0,
        )
        return

    if normalized == "issue":
        subcommand = "reopen" if bool(open_state) else "close"
        run_gh_gh(
            [
                "issue",
                subcommand,
                str(int(number)),
                "--repo",
                repo,
            ],
            timeout_s=45.0,
        )
        return

    raise GhManagementError(f"unsupported item type: {item_type}")


def add_issue_comment_reaction(
    repo_owner: str,
    repo_name: str,
    *,
    comment_id: int,
    reaction: str,
) -> None:
    repo = _repo_full_name(repo_owner, repo_name)
    reaction_value = _safe_text(reaction)
    if reaction_value not in {"+1", "-1", "eyes", "rocket", "hooray"}:
        raise GhManagementError(f"unsupported reaction: {reaction_value}")

    run_gh_gh_json(
        [
            "api",
            "--method",
            "POST",
            f"repos/{repo}/issues/comments/{int(comment_id)}/reactions",
            "-H",
            "Accept: application/vnd.github+json",
            "-f",
            f"content={reaction_value}",
        ],
        timeout_s=30.0,
    )


def get_authenticated_github_login() -> str:
    """Return the currently authenticated ``gh`` login (or empty string)."""
    try:
        data = run_gh_gh_json(
            [
                "api",
                "user",
                "-H",
                "Accept: application/vnd.github+json",
            ],
            timeout_s=20.0,
        )
    except Exception:
        return ""
    if not isinstance(data, dict):
        return ""
    return _safe_text(data.get("login")).lower()


def list_org_members(owner: str, *, limit: int = 100) -> list[str]:
    """Best-effort list of org members for ``owner``.

    Returns an empty list when owner is not an organization or when API access
    is unavailable.
    """
    owner_text = _safe_text(owner)
    if not owner_text:
        return []
    try:
        per_page = max(1, min(100, int(limit)))
    except Exception:
        per_page = 100

    try:
        data = run_gh_gh_json(
            [
                "api",
                f"orgs/{owner_text}/members?per_page={per_page}",
                "-H",
                "Accept: application/vnd.github+json",
            ],
            timeout_s=30.0,
        )
    except Exception:
        return []

    rows = data if isinstance(data, list) else []
    members: list[str] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        login = _safe_text(row.get("login")).lower()
        if not login or login in seen:
            continue
        members.append(login)
        seen.add(login)
    return members
