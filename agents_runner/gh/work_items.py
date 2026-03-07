from __future__ import annotations

import json
import random
import time

from dataclasses import dataclass
from typing import Any
from typing import cast

from .auth import resolve_authenticated_login
from .errors import GhManagementError
from .process import run_gh

AUTO_REVIEW_MARKER_TOKEN = "<!-- midori-ai-agents-runner-auto-review-marker -->"
_READ_RETRY_MAX_ATTEMPTS = 4
_READ_RETRY_BASE_DELAY_S = 1.0
_READ_RETRY_JITTER_RATIO = 0.25

_NON_RETRYABLE_GH_ERROR_MARKERS = (
    "authentication",
    "unauthorized",
    "forbidden",
    "bad credentials",
    "not found",
    "validation failed",
    "resource not accessible",
    "graphql: could not resolve",
    "graphql: not found",
    "insufficient scopes",
    "requires authentication",
)

_TRANSIENT_GH_ERROR_MARKERS = (
    "timed out",
    "i/o timeout",
    "dial tcp",
    "temporary failure",
    "network is unreachable",
    "connection reset",
    "connection refused",
    "connection aborted",
    "no such host",
    "tls handshake timeout",
    "context deadline exceeded",
)

_GITHUB_API_PER_PAGE_MAX = 100
_REACTION_SCAN_LIMIT = 1000


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
class GitHubReview:
    review_id: int
    body: str
    author: str
    submitted_at: str
    url: str


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
    head_ref: str = ""
    base_ref: str = ""
    head_repo_owner: str = ""
    head_repo_name: str = ""
    is_cross_repo: bool = False


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


def _as_object_dict(value: object) -> dict[object, object] | None:
    if not isinstance(value, dict):
        return None
    return cast(dict[object, object], value)


def _as_object_list(value: object) -> list[object] | None:
    if not isinstance(value, list):
        return None
    return cast(list[object], value)


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(cast(Any, value))
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


def _is_retryable_read_error(exc: Exception) -> bool:
    if isinstance(exc, (TimeoutError, OSError)):
        return True
    if not isinstance(exc, GhManagementError):
        return False
    text = str(exc or "").strip().lower()
    if not text:
        return False
    if any(marker in text for marker in _NON_RETRYABLE_GH_ERROR_MARKERS):
        return False
    return any(marker in text for marker in _TRANSIENT_GH_ERROR_MARKERS)


def run_gh_gh_json_read(
    args: list[str], *, timeout_s: float = 45.0, retry_on_transient: bool = True
) -> object:
    max_attempts = _READ_RETRY_MAX_ATTEMPTS if retry_on_transient else 1
    last_exc: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            return run_gh_gh_json(args, timeout_s=timeout_s)
        except Exception as exc:
            if not retry_on_transient or not _is_retryable_read_error(exc):
                raise
            last_exc = exc
            if attempt >= max_attempts:
                raise
            base_delay = _READ_RETRY_BASE_DELAY_S * (2 ** (attempt - 1))
            jitter = random.uniform(0.0, base_delay * _READ_RETRY_JITTER_RATIO)
            time.sleep(base_delay + jitter)

    if last_exc is not None:
        raise last_exc
    raise GhManagementError(f"gh command failed: {' '.join(args)}")


def _parse_reaction_summary(raw: object) -> GitHubReactionSummary:
    raw_dict = _as_object_dict(raw)
    if raw_dict is not None:
        return GitHubReactionSummary(
            thumbs_up=max(0, _safe_int(raw_dict.get("+1"))),
            thumbs_down=max(0, _safe_int(raw_dict.get("-1"))),
            eyes=max(0, _safe_int(raw_dict.get("eyes"))),
            rocket=max(0, _safe_int(raw_dict.get("rocket"))),
            hooray=max(0, _safe_int(raw_dict.get("hooray"))),
        )

    groups = _as_object_list(raw) or []
    up = 0
    down = 0
    eyes = 0
    rocket = 0
    hooray = 0
    for item in groups:
        item_dict = _as_object_dict(item)
        if item_dict is None:
            continue
        content = _safe_text(item_dict.get("content")).upper()
        total = 0
        users_dict = _as_object_dict(item_dict.get("users"))
        if users_dict is not None:
            total = _safe_int(users_dict.get("totalCount"))
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
    raw_dict = _as_object_dict(raw)
    if raw_dict is None:
        return None

    number = _safe_int(raw_dict.get("number"))
    if number <= 0:
        return None

    author = ""
    raw_author = _as_object_dict(raw_dict.get("author"))
    if raw_author is not None:
        author = _safe_text(raw_author.get("login"))

    head_ref = ""
    base_ref = ""
    head_repo_owner = ""
    head_repo_name = ""
    is_cross_repo = False
    if item_type == "pr":
        head_ref = _safe_text(raw_dict.get("headRefName"))
        base_ref = _safe_text(raw_dict.get("baseRefName"))
        is_cross_repo = bool(raw_dict.get("isCrossRepository") or False)

        head_repo_owner_data = raw_dict.get("headRepositoryOwner")
        if isinstance(head_repo_owner_data, str):
            head_repo_owner = _safe_text(head_repo_owner_data)
        else:
            owner_dict = _as_object_dict(head_repo_owner_data)
            if owner_dict is not None:
                head_repo_owner = _safe_text(owner_dict.get("login"))

        head_repo_data = raw_dict.get("headRepository")
        if isinstance(head_repo_data, str):
            head_repo_text = _safe_text(head_repo_data)
            if "/" in head_repo_text:
                owner_part, name_part = head_repo_text.split("/", 1)
                if not head_repo_owner:
                    head_repo_owner = _safe_text(owner_part)
                head_repo_name = _safe_text(name_part)
            else:
                head_repo_name = head_repo_text
        else:
            repo_dict = _as_object_dict(head_repo_data)
            if repo_dict is not None:
                head_repo_name = _safe_text(repo_dict.get("name"))
                if not head_repo_owner:
                    repo_owner = _as_object_dict(repo_dict.get("owner"))
                    if repo_owner is not None:
                        head_repo_owner = _safe_text(repo_owner.get("login"))

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
        head_ref=head_ref,
        base_ref=base_ref,
        head_repo_owner=head_repo_owner,
        head_repo_name=head_repo_name,
        is_cross_repo=is_cross_repo,
    )


def _repo_full_name(repo_owner: str, repo_name: str) -> str:
    owner = _safe_text(repo_owner)
    name = _safe_text(repo_name)
    if not owner or not name:
        raise GhManagementError("missing repository owner/name")
    return f"{owner}/{name}"


def _with_api_pagination(path: str, *, page: int, per_page: int) -> str:
    delimiter = "&" if "?" in path else "?"
    return f"{path}{delimiter}per_page={max(1, int(per_page))}&page={max(1, int(page))}"


def _list_api_rows_paginated(
    path: str,
    *,
    limit: int,
    keep_latest: bool = False,
    timeout_s: float = 45.0,
    retry_on_transient: bool = True,
) -> list[object]:
    safe_limit = max(1, int(limit))
    per_page = min(_GITHUB_API_PER_PAGE_MAX, safe_limit)
    rows: list[object] = []
    page = 1

    while True:
        data = run_gh_gh_json_read(
            [
                "api",
                _with_api_pagination(path, page=page, per_page=per_page),
                "-H",
                "Accept: application/vnd.github+json",
            ],
            timeout_s=timeout_s,
            retry_on_transient=retry_on_transient,
        )
        page_rows = _as_object_list(data) or []
        if not page_rows:
            break
        rows.extend(page_rows)
        if keep_latest and len(rows) > safe_limit:
            rows = rows[-safe_limit:]
        if not keep_latest and len(rows) >= safe_limit:
            break
        if len(page_rows) < per_page:
            break
        page += 1

    if keep_latest:
        return rows
    return rows[:safe_limit]


def _has_reaction_on_endpoint(
    repo_owner: str,
    repo_name: str,
    *,
    endpoint: str,
    reaction: str,
    actor_login: str | None = None,
    limit: int = _REACTION_SCAN_LIMIT,
    retry_on_transient: bool = True,
) -> bool:
    repo = _repo_full_name(repo_owner, repo_name)
    content_value = _safe_text(reaction).lower()
    if content_value not in {"+1", "-1", "eyes", "rocket", "hooray"}:
        raise GhManagementError(f"unsupported reaction: {content_value}")
    actor = _safe_text(actor_login).lower()
    actor_filter_enabled = bool(actor)

    rows = _list_api_rows_paginated(
        f"repos/{repo}/{endpoint}",
        limit=limit,
        timeout_s=45.0,
        retry_on_transient=retry_on_transient,
    )
    for row in rows:
        row_dict = _as_object_dict(row)
        if row_dict is None:
            continue
        content = _safe_text(row_dict.get("content")).lower()
        if content != content_value:
            continue
        if not actor_filter_enabled:
            return True
        user_dict = _as_object_dict(row_dict.get("user"))
        user_login = _safe_text(user_dict.get("login") if user_dict else "").lower()
        if user_login == actor:
            return True
    return False


def list_open_pull_requests(
    repo_owner: str,
    repo_name: str,
    *,
    limit: int = 30,
) -> list[GitHubWorkItem]:
    repo = _repo_full_name(repo_owner, repo_name)
    data = run_gh_gh_json_read(
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
            (
                "number,title,body,state,url,author,createdAt,updatedAt,isDraft,"
                "headRefName,baseRefName,isCrossRepository,headRepository,headRepositoryOwner"
            ),
        ],
        timeout_s=45.0,
        retry_on_transient=True,
    )

    rows = _as_object_list(data) or []
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
    data = run_gh_gh_json_read(
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
        retry_on_transient=True,
    )

    rows = _as_object_list(data) or []
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
    newest_first: bool = False,
    retry_on_transient: bool = True,
) -> list[GitHubComment]:
    repo = _repo_full_name(repo_owner, repo_name)
    rows = _list_api_rows_paginated(
        f"repos/{repo}/issues/{int(issue_number)}/comments",
        limit=limit,
        keep_latest=newest_first,
        timeout_s=45.0,
        retry_on_transient=retry_on_transient,
    )
    comments: list[GitHubComment] = []
    for row in rows:
        row_dict = _as_object_dict(row)
        if row_dict is None:
            continue

        comment_id = _safe_int(row_dict.get("id"))
        if comment_id <= 0:
            continue

        user_dict = _as_object_dict(row_dict.get("user"))
        author = _safe_text(user_dict.get("login") if user_dict is not None else "")

        comments.append(
            GitHubComment(
                comment_id=comment_id,
                node_id=_safe_text(row_dict.get("node_id")),
                body=_safe_text(row_dict.get("body")),
                author=author,
                created_at=_safe_text(row_dict.get("created_at")),
                updated_at=_safe_text(row_dict.get("updated_at")),
                url=_safe_text(row_dict.get("html_url")),
                reactions=_parse_reaction_summary(row_dict.get("reactions")),
            )
        )

    return comments


def list_pull_request_review_comments(
    repo_owner: str,
    repo_name: str,
    *,
    pull_number: int,
    limit: int = 100,
    newest_first: bool = False,
    retry_on_transient: bool = True,
) -> list[GitHubComment]:
    repo = _repo_full_name(repo_owner, repo_name)
    rows = _list_api_rows_paginated(
        f"repos/{repo}/pulls/{int(pull_number)}/comments",
        limit=limit,
        keep_latest=newest_first,
        timeout_s=45.0,
        retry_on_transient=retry_on_transient,
    )
    comments: list[GitHubComment] = []
    for row in rows:
        row_dict = _as_object_dict(row)
        if row_dict is None:
            continue

        comment_id = _safe_int(row_dict.get("id"))
        if comment_id <= 0:
            continue

        user_dict = _as_object_dict(row_dict.get("user"))
        author = _safe_text(user_dict.get("login") if user_dict is not None else "")

        comments.append(
            GitHubComment(
                comment_id=comment_id,
                node_id=_safe_text(row_dict.get("node_id")),
                body=_safe_text(row_dict.get("body")),
                author=author,
                created_at=_safe_text(row_dict.get("created_at")),
                updated_at=_safe_text(row_dict.get("updated_at")),
                url=_safe_text(row_dict.get("html_url")),
                reactions=_parse_reaction_summary(row_dict.get("reactions")),
            )
        )

    return comments


def list_pull_request_reviews(
    repo_owner: str,
    repo_name: str,
    *,
    pull_number: int,
    limit: int = 100,
    newest_first: bool = False,
    retry_on_transient: bool = True,
) -> list[GitHubReview]:
    repo = _repo_full_name(repo_owner, repo_name)
    rows = _list_api_rows_paginated(
        f"repos/{repo}/pulls/{int(pull_number)}/reviews",
        limit=limit,
        keep_latest=newest_first,
        timeout_s=45.0,
        retry_on_transient=retry_on_transient,
    )
    reviews: list[GitHubReview] = []
    for row in rows:
        row_dict = _as_object_dict(row)
        if row_dict is None:
            continue

        review_id = _safe_int(row_dict.get("id"))
        if review_id <= 0:
            continue

        user_dict = _as_object_dict(row_dict.get("user"))
        author = _safe_text(user_dict.get("login") if user_dict is not None else "")

        url = _safe_text(row_dict.get("html_url")) or _safe_text(row_dict.get("url"))

        reviews.append(
            GitHubReview(
                review_id=review_id,
                body=_safe_text(row_dict.get("body")),
                author=author,
                submitted_at=_safe_text(row_dict.get("submitted_at")),
                url=url,
            )
        )

    return reviews


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
    data_dict = _as_object_dict(data)
    if data_dict is None:
        raise GhManagementError("invalid pull request payload")

    author = ""
    raw_author = _as_object_dict(data_dict.get("author"))
    if raw_author is not None:
        author = _safe_text(raw_author.get("login"))

    comments = list_issue_comments(
        repo_owner,
        repo_name,
        issue_number=int(number),
        limit=100,
        retry_on_transient=False,
    )

    return GitHubWorkroom(
        item_type="pr",
        repo_owner=_safe_text(repo_owner),
        repo_name=_safe_text(repo_name),
        number=max(1, _safe_int(data_dict.get("number"), int(number))),
        title=_safe_text(data_dict.get("title")) or f"PR #{int(number)}",
        body=_safe_text(data_dict.get("body")),
        state=_safe_text(data_dict.get("state")).lower() or "open",
        url=_safe_text(data_dict.get("url")),
        author=author,
        created_at=_safe_text(data_dict.get("createdAt")),
        updated_at=_safe_text(data_dict.get("updatedAt")),
        is_draft=bool(data_dict.get("isDraft") or False),
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
    data_dict = _as_object_dict(data)
    if data_dict is None:
        raise GhManagementError("invalid issue payload")

    author = ""
    raw_author = _as_object_dict(data_dict.get("author"))
    if raw_author is not None:
        author = _safe_text(raw_author.get("login"))

    comments = list_issue_comments(
        repo_owner,
        repo_name,
        issue_number=int(number),
        limit=100,
        retry_on_transient=False,
    )

    return GitHubWorkroom(
        item_type="issue",
        repo_owner=_safe_text(repo_owner),
        repo_name=_safe_text(repo_name),
        number=max(1, _safe_int(data_dict.get("number"), int(number))),
        title=_safe_text(data_dict.get("title")) or f"Issue #{int(number)}",
        body=_safe_text(data_dict.get("body")),
        state=_safe_text(data_dict.get("state")).lower() or "open",
        url=_safe_text(data_dict.get("url")),
        author=author,
        created_at=_safe_text(data_dict.get("createdAt")),
        updated_at=_safe_text(data_dict.get("updatedAt")),
        is_draft=False,
        comments=comments,
    )


def post_comment_with_id(
    repo_owner: str,
    repo_name: str,
    *,
    item_type: str,
    number: int,
    body: str,
) -> int:
    repo = _repo_full_name(repo_owner, repo_name)
    text = _safe_text(body)
    if not text:
        raise GhManagementError("comment body is empty")

    normalized = _safe_text(item_type).lower()
    if normalized not in {"issue", "pr"}:
        raise GhManagementError(f"unsupported item type: {item_type}")

    data = run_gh_gh_json(
        [
            "api",
            "--method",
            "POST",
            f"repos/{repo}/issues/{int(number)}/comments",
            "-H",
            "Accept: application/vnd.github+json",
            "-f",
            f"body={text}",
        ],
        timeout_s=45.0,
    )
    data_dict = _as_object_dict(data)
    comment_id = _safe_int(data_dict.get("id") if data_dict is not None else 0)
    if comment_id <= 0:
        raise GhManagementError("comment create succeeded without returning an id")
    return comment_id


def post_comment(
    repo_owner: str,
    repo_name: str,
    *,
    item_type: str,
    number: int,
    body: str,
) -> None:
    _ = post_comment_with_id(
        repo_owner,
        repo_name,
        item_type=item_type,
        number=number,
        body=body,
    )


def delete_issue_comment(
    repo_owner: str,
    repo_name: str,
    *,
    comment_id: int,
) -> None:
    repo = _repo_full_name(repo_owner, repo_name)
    comment_id_value = int(comment_id)
    if comment_id_value <= 0:
        raise GhManagementError("invalid comment id")

    run_gh_gh(
        [
            "api",
            "--method",
            "DELETE",
            f"repos/{repo}/issues/comments/{comment_id_value}",
            "-H",
            "Accept: application/vnd.github+json",
        ],
        timeout_s=30.0,
    )


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


def add_pull_request_review_comment_reaction(
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
            f"repos/{repo}/pulls/comments/{int(comment_id)}/reactions",
            "-H",
            "Accept: application/vnd.github+json",
            "-f",
            f"content={reaction_value}",
        ],
        timeout_s=30.0,
    )


def add_pull_request_review_reaction(
    repo_owner: str,
    repo_name: str,
    *,
    pull_number: int,
    review_id: int,
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
            f"repos/{repo}/pulls/{int(pull_number)}/reviews/{int(review_id)}/reactions",
            "-H",
            "Accept: application/vnd.github+json",
            "-f",
            f"content={reaction_value}",
        ],
        timeout_s=30.0,
    )


def add_issue_reaction(
    repo_owner: str,
    repo_name: str,
    *,
    issue_number: int,
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
            f"repos/{repo}/issues/{int(issue_number)}/reactions",
            "-H",
            "Accept: application/vnd.github+json",
            "-f",
            f"content={reaction_value}",
        ],
        timeout_s=30.0,
    )


def has_actor_issue_reaction(
    repo_owner: str,
    repo_name: str,
    *,
    issue_number: int,
    reaction: str,
    actor_login: str,
    limit: int = _REACTION_SCAN_LIMIT,
    retry_on_transient: bool = True,
) -> bool:
    actor = _safe_text(actor_login).lower()
    if not actor:
        raise GhManagementError("missing actor login for reaction check")
    return _has_reaction_on_endpoint(
        repo_owner,
        repo_name,
        endpoint=f"issues/{int(issue_number)}/reactions",
        reaction=reaction,
        actor_login=actor,
        limit=limit,
        retry_on_transient=retry_on_transient,
    )


def has_actor_issue_comment_reaction(
    repo_owner: str,
    repo_name: str,
    *,
    comment_id: int,
    reaction: str,
    actor_login: str,
    limit: int = _REACTION_SCAN_LIMIT,
    retry_on_transient: bool = True,
) -> bool:
    actor = _safe_text(actor_login).lower()
    if not actor:
        raise GhManagementError("missing actor login for reaction check")
    return _has_reaction_on_endpoint(
        repo_owner,
        repo_name,
        endpoint=f"issues/comments/{int(comment_id)}/reactions",
        reaction=reaction,
        actor_login=actor,
        limit=limit,
        retry_on_transient=retry_on_transient,
    )


def has_actor_pull_request_review_comment_reaction(
    repo_owner: str,
    repo_name: str,
    *,
    comment_id: int,
    reaction: str,
    actor_login: str,
    limit: int = _REACTION_SCAN_LIMIT,
    retry_on_transient: bool = True,
) -> bool:
    actor = _safe_text(actor_login).lower()
    if not actor:
        raise GhManagementError("missing actor login for reaction check")
    return _has_reaction_on_endpoint(
        repo_owner,
        repo_name,
        endpoint=f"pulls/comments/{int(comment_id)}/reactions",
        reaction=reaction,
        actor_login=actor,
        limit=limit,
        retry_on_transient=retry_on_transient,
    )


def has_actor_pull_request_review_reaction(
    repo_owner: str,
    repo_name: str,
    *,
    pull_number: int,
    review_id: int,
    reaction: str,
    actor_login: str,
    limit: int = _REACTION_SCAN_LIMIT,
    retry_on_transient: bool = True,
) -> bool:
    actor = _safe_text(actor_login).lower()
    if not actor:
        raise GhManagementError("missing actor login for reaction check")
    return _has_reaction_on_endpoint(
        repo_owner,
        repo_name,
        endpoint=f"pulls/{int(pull_number)}/reviews/{int(review_id)}/reactions",
        reaction=reaction,
        actor_login=actor,
        limit=limit,
        retry_on_transient=retry_on_transient,
    )


def has_issue_reaction(
    repo_owner: str,
    repo_name: str,
    *,
    issue_number: int,
    reaction: str,
    limit: int = _REACTION_SCAN_LIMIT,
    retry_on_transient: bool = True,
) -> bool:
    return _has_reaction_on_endpoint(
        repo_owner,
        repo_name,
        endpoint=f"issues/{int(issue_number)}/reactions",
        reaction=reaction,
        limit=limit,
        retry_on_transient=retry_on_transient,
    )


def has_pull_request_review_reaction(
    repo_owner: str,
    repo_name: str,
    *,
    pull_number: int,
    review_id: int,
    reaction: str,
    limit: int = _REACTION_SCAN_LIMIT,
    retry_on_transient: bool = True,
) -> bool:
    return _has_reaction_on_endpoint(
        repo_owner,
        repo_name,
        endpoint=f"pulls/{int(pull_number)}/reviews/{int(review_id)}/reactions",
        reaction=reaction,
        limit=limit,
        retry_on_transient=retry_on_transient,
    )


def get_authenticated_github_login() -> str:
    """Return the currently authenticated ``gh`` login (or empty string)."""
    try:
        return resolve_authenticated_login(timeout_s=20.0, use_cache=True)
    except Exception:
        return ""


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

    rows = _as_object_list(data) or []
    members: list[str] = []
    seen: set[str] = set()
    for row in rows:
        row_dict = _as_object_dict(row)
        if row_dict is None:
            continue
        login = _safe_text(row_dict.get("login")).lower()
        if not login or login in seen:
            continue
        members.append(login)
        seen.add(login)
    return members
