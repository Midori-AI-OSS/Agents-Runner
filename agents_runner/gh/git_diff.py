from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .process import _run, _expand_dir


@dataclass
class ChangedFile:
    path: str
    status: str  # A=Added, M=Modified, D=Deleted, R=Renamed, U=Untracked


def git_merge_base(repo_root: str, base_ref: str) -> str | None:
    """Get merge-base commit SHA between HEAD and base_ref."""
    expanded = _expand_dir(repo_root)
    proc = _run(["git", "merge-base", "HEAD", base_ref], cwd=expanded)
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def git_changed_files(repo_root: str, base_commit: str) -> list[ChangedFile]:
    """Get list of changed files vs base_commit.

    Combines:
    - git diff --name-status <base_commit>...HEAD (committed changes)
    - git diff --name-status <base_commit> (includes staged/unstaged)
    - git ls-files --others --exclude-standard (untracked)

    Returns unique list with stable order.
    """
    expanded = _expand_dir(repo_root)
    files: dict[str, str] = {}

    # Get committed changes (base_commit...HEAD)
    proc = _run(
        ["git", "diff", "--name-status", f"{base_commit}...HEAD"], cwd=expanded
    )
    if proc.returncode == 0:
        for line in proc.stdout.strip().split("\n"):
            if not line:
                continue
            parts = line.split("\t", 1)
            if len(parts) == 2:
                status, path = parts
                files[path] = status[0]  # First char: A/M/D/R

    # Get all changes including staged/unstaged (base_commit vs working tree)
    proc = _run(["git", "diff", "--name-status", base_commit], cwd=expanded)
    if proc.returncode == 0:
        for line in proc.stdout.strip().split("\n"):
            if not line:
                continue
            parts = line.split("\t", 1)
            if len(parts) == 2:
                status, path = parts
                # Update status if file wasn't already tracked or is more specific
                if path not in files:
                    files[path] = status[0]

    # Get untracked files
    proc = _run(
        ["git", "ls-files", "--others", "--exclude-standard"], cwd=expanded
    )
    if proc.returncode == 0:
        for line in proc.stdout.strip().split("\n"):
            if line and line not in files:
                files[line] = "U"

    # Convert to list with stable order (alphabetical)
    return [
        ChangedFile(path=path, status=status)
        for path, status in sorted(files.items())
    ]


def git_file_at_commit(repo_root: str, commit: str, path: str) -> str | None:
    """Get file content at specific commit.

    Uses: git show <commit>:<path>
    Returns file content or None if file doesn't exist at commit.
    """
    expanded = _expand_dir(repo_root)
    proc = _run(["git", "show", f"{commit}:{path}"], cwd=expanded)
    if proc.returncode != 0:
        return None

    # Check if binary
    output_bytes = proc.stdout.encode("utf-8", errors="surrogateescape")
    if is_binary_file(output_bytes[:8192]):
        return None

    return proc.stdout


def read_workspace_file(repo_root: str, path: str) -> str | None:
    """Read current file content from disk.

    Returns file content or None if file doesn't exist.
    Handles binary detection and size limits (max 1MB).
    Returns None for binary files.
    """
    expanded = _expand_dir(repo_root)
    full_path = Path(expanded) / path

    try:
        if not full_path.is_file():
            return None

        # Check file size (max 1MB)
        size = full_path.stat().st_size
        if size > 1024 * 1024:
            return None

        # Read first 8KB to check if binary
        with full_path.open("rb") as f:
            header = f.read(8192)
            if is_binary_file(header):
                return None

        # Read full content as text
        return full_path.read_text(encoding="utf-8", errors="replace")

    except (OSError, UnicodeDecodeError):
        return None


def is_binary_file(content: bytes) -> bool:
    """Check if content appears to be binary (contains null bytes in first 8KB)."""
    return b"\x00" in content
