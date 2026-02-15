import os

from .process import expand_dir, run_gh


def is_git_repo(path: str) -> bool:
    path = expand_dir(path)
    if not os.path.isdir(path):
        return False
    proc = run_gh(
        ["git", "-C", path, "rev-parse", "--is-inside-work-tree"], timeout_s=8.0
    )
    return proc.returncode == 0 and (proc.stdout or "").strip().lower() == "true"


def git_repo_root(path: str) -> str | None:
    path = expand_dir(path)
    if not os.path.isdir(path):
        return None
    proc = run_gh(["git", "-C", path, "rev-parse", "--show-toplevel"], timeout_s=8.0)
    if proc.returncode != 0:
        return None
    root = (proc.stdout or "").strip()
    return root if root else None


def git_current_branch(repo_root: str) -> str | None:
    repo_root = expand_dir(repo_root)
    proc = run_gh(
        ["git", "-C", repo_root, "rev-parse", "--abbrev-ref", "HEAD"], timeout_s=8.0
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
    if (
        "://" not in url
        and not url.startswith("git@")
        and "/" in url
        and " " not in url
    ):
        url = f"https://github.com/{url}.git"
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


def git_head_commit(repo_root: str) -> str | None:
    """Get HEAD commit SHA.

    Returns full 40-character SHA if successful, None on error.
    Timeout: 8 seconds.
    """
    repo_root = expand_dir(repo_root)
    proc = run_gh(["git", "-C", repo_root, "rev-parse", "HEAD"], timeout_s=8.0)
    if proc.returncode != 0:
        return None
    sha = (proc.stdout or "").strip()
    return sha if sha else None


def git_remote_url(repo_root: str, remote: str = "origin") -> str | None:
    """Get remote URL for a given remote name.

    Returns URL string if remote exists, None otherwise.
    Timeout: 8 seconds.
    """
    repo_root = expand_dir(repo_root)
    proc = run_gh(["git", "-C", repo_root, "remote", "get-url", remote], timeout_s=8.0)
    if proc.returncode != 0:
        return None
    url = (proc.stdout or "").strip()
    return url if url else None


def parse_github_url(url: str) -> tuple[str | None, str | None]:
    """Parse owner and repo name from GitHub URL.

    Supports multiple URL formats:
        - https://github.com/owner/repo
        - https://github.com/owner/repo.git
        - git@github.com:owner/repo.git
        - ssh://git@github.com/owner/repo

    Returns (owner, repo_name) tuple, or (None, None) if parsing fails.
    """
    import re

    url = (url or "").strip()
    if not url:
        return None, None

    # HTTPS pattern: https://github.com/owner/repo or https://github.com/owner/repo.git
    https_match = re.search(r"github\.com[:/]([^/]+)/([^/\.]+)", url)
    if https_match:
        owner = https_match.group(1).strip()
        repo = https_match.group(2).strip()
        # Remove .git suffix if present
        if repo.endswith(".git"):
            repo = repo[:-4]
        return owner if owner else None, repo if repo else None

    # SSH pattern: git@github.com:owner/repo.git
    ssh_match = re.search(r"github\.com:([^/]+)/([^/\.]+)", url)
    if ssh_match:
        owner = ssh_match.group(1).strip()
        repo = ssh_match.group(2).strip()
        # Remove .git suffix if present
        if repo.endswith(".git"):
            repo = repo[:-4]
        return owner if owner else None, repo if repo else None

    return None, None
