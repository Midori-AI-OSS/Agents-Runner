import os
import re
from urllib.parse import urlsplit

from .process import expand_dir, run_gh

_GITHUB_REPO_PART_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")


def _parse_github_repo_path(path: str) -> tuple[str | None, str | None]:
    candidate = str(path or "").strip().strip("/")
    if not candidate:
        return None, None
    if candidate.endswith(".git"):
        candidate = candidate[: -len(".git")].strip().strip("/")
    parts = [part.strip() for part in candidate.split("/") if part.strip()]
    if len(parts) != 2:
        return None, None
    owner, repo = parts
    if not _GITHUB_REPO_PART_PATTERN.fullmatch(owner):
        return None, None
    if not _GITHUB_REPO_PART_PATTERN.fullmatch(repo):
        return None, None
    return owner, repo


def is_git_repo(path: str, *, timeout_s: float = 8.0) -> bool:
    path = expand_dir(path)
    if not os.path.isdir(path):
        return False
    proc = run_gh(
        ["git", "-C", path, "rev-parse", "--is-inside-work-tree"], timeout_s=timeout_s
    )
    return proc.returncode == 0 and (proc.stdout or "").strip().lower() == "true"


def git_repo_root(path: str, *, timeout_s: float = 8.0) -> str | None:
    path = expand_dir(path)
    if not os.path.isdir(path):
        return None
    proc = run_gh(
        ["git", "-C", path, "rev-parse", "--show-toplevel"], timeout_s=timeout_s
    )
    if proc.returncode != 0:
        return None
    root = (proc.stdout or "").strip()
    return root if root else None


def git_current_branch(repo_root: str, *, timeout_s: float = 8.0) -> str | None:
    repo_root = expand_dir(repo_root)
    proc = run_gh(
        ["git", "-C", repo_root, "rev-parse", "--abbrev-ref", "HEAD"],
        timeout_s=timeout_s,
    )
    if proc.returncode != 0:
        return None
    branch = (proc.stdout or "").strip()
    if not branch or branch == "HEAD":
        return None
    return branch


def git_default_base_branch(repo_root: str) -> str | None:
    repo_root = expand_dir(repo_root)
    proc = run_gh(
        ["git", "-C", repo_root, "symbolic-ref", "--short", "refs/remotes/origin/HEAD"],
        timeout_s=8.0,
    )
    if proc.returncode != 0:
        return None
    ref = (proc.stdout or "").strip()
    if not ref.startswith("origin/"):
        return None
    branch = ref.removeprefix("origin/").strip()
    return branch or None


def git_is_clean(repo_root: str) -> bool:
    repo_root = expand_dir(repo_root)
    proc = run_gh(["git", "-C", repo_root, "status", "--porcelain"], timeout_s=15.0)
    if proc.returncode != 0:
        return False
    return not (proc.stdout or "").strip()


def git_list_branches(repo_root: str) -> list[str]:
    repo_root = expand_dir(repo_root)
    proc = run_gh(
        [
            "git",
            "-C",
            repo_root,
            "for-each-ref",
            "--format=%(refname:short)",
            "refs/heads",
            "refs/remotes",
        ],
        timeout_s=10.0,
    )
    if proc.returncode != 0:
        return []
    branches: list[str] = []
    seen: set[str] = set()
    for raw in (proc.stdout or "").splitlines():
        name = (raw or "").strip()
        if not name or name.endswith("/HEAD") or name == "HEAD":
            continue
        if name.startswith("origin/"):
            name = name.removeprefix("origin/").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        branches.append(name)
    return sorted(branches, key=str.casefold)


def git_list_remote_heads(repo: str) -> list[str]:
    repo = (repo or "").strip()
    if not repo:
        return []
    url = repo
    if "://" not in url and not url.startswith("git@"):
        owner, repo_name = parse_github_url(url)
        if owner and repo_name:
            url = f"https://github.com/{owner}/{repo_name}.git"
    proc = run_gh(["git", "ls-remote", "--heads", url], timeout_s=20.0)
    if proc.returncode != 0:
        return []
    branches: list[str] = []
    seen: set[str] = set()
    for line in (proc.stdout or "").splitlines():
        parts = (line or "").strip().split()
        if len(parts) != 2:
            continue
        ref = parts[1].strip()
        if not ref.startswith("refs/heads/"):
            continue
        name = ref.removeprefix("refs/heads/").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        branches.append(name)
    return sorted(branches, key=str.casefold)


def git_head_commit(repo_root: str, *, timeout_s: float = 8.0) -> str | None:
    """Get HEAD commit SHA.

    Returns full 40-character SHA if successful, None on error.
    Timeout: 8 seconds.
    """
    repo_root = expand_dir(repo_root)
    proc = run_gh(["git", "-C", repo_root, "rev-parse", "HEAD"], timeout_s=timeout_s)
    if proc.returncode != 0:
        return None
    sha = (proc.stdout or "").strip()
    return sha if sha else None


def git_remote_url(
    repo_root: str, remote: str = "origin", *, timeout_s: float = 8.0
) -> str | None:
    """Get remote URL for a given remote name.

    Returns URL string if remote exists, None otherwise.
    Timeout: 8 seconds.
    """
    repo_root = expand_dir(repo_root)
    proc = run_gh(
        ["git", "-C", repo_root, "remote", "get-url", remote], timeout_s=timeout_s
    )
    if proc.returncode != 0:
        return None
    url = (proc.stdout or "").strip()
    return url if url else None


def parse_github_url(url: str) -> tuple[str | None, str | None]:
    """Parse owner and repo name from GitHub references.

    Supports multiple URL formats:
        - owner/repo
        - https://github.com/owner/repo
        - https://github.com/owner/repo.git
        - git@github.com:owner/repo.git
        - ssh://git@github.com/owner/repo

    Returns (owner, repo_name) tuple, or (None, None) if parsing fails.
    Only exact GitHub hosts are accepted for URL forms, and paths must be
    exactly two segments (`owner/repo`) after an optional terminal `.git`.
    """
    text = (url or "").strip()
    if not text or " " in text:
        return None, None

    if "://" not in text and not text.startswith("git@"):
        return _parse_github_repo_path(text)

    if text.startswith("git@"):
        prefix = "git@github.com:"
        if not text.startswith(prefix):
            return None, None
        path = text[len(prefix) :].split("#", 1)[0].split("?", 1)[0]
        return _parse_github_repo_path(path)

    parsed = urlsplit(text)
    if parsed.scheme not in {"http", "https", "ssh"}:
        return None, None
    if (parsed.hostname or "").lower() != "github.com":
        return None, None
    if parsed.scheme == "ssh" and (parsed.username or "") != "git":
        return None, None
    return _parse_github_repo_path(parsed.path)


def normalize_github_repo_slug(value: str) -> str:
    owner, repo = parse_github_url(value)
    if not owner or not repo:
        return ""
    return f"{owner.lower()}/{repo.lower()}"
