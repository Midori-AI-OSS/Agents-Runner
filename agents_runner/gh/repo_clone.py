import os
import subprocess
import time

from .errors import GhManagementError
from .gh_cli import is_gh_available
from .git_ops import is_git_repo
from .process import _expand_dir, _is_empty_dir, _require_ok, _run


def ensure_github_clone(
    repo: str,
    dest_dir: str,
    *,
    prefer_gh: bool = True,
    recreate_if_needed: bool = False,
) -> None:
    repo = (repo or "").strip()
    if not repo:
        raise GhManagementError("missing GitHub repo")
    dest_dir = _expand_dir(dest_dir)
    parent = os.path.dirname(dest_dir)
    os.makedirs(parent, exist_ok=True)
    if os.path.exists(dest_dir):
        if is_git_repo(dest_dir):
            return
        if os.path.isfile(dest_dir):
            raise GhManagementError(f"destination exists but is a file: {dest_dir}")
        if _is_empty_dir(dest_dir):
            try:
                os.rmdir(dest_dir)
            except OSError:
                pass
        elif recreate_if_needed and os.path.isdir(dest_dir):
            backup_dir = f"{dest_dir}.bak-{time.time_ns()}"
            try:
                os.replace(dest_dir, backup_dir)
            except OSError as exc:
                raise GhManagementError(
                    f"destination exists but is not a git repo: {dest_dir}\n"
                    f"failed to move it aside to {backup_dir}: {exc}"
                ) from exc
        else:
            raise GhManagementError(
                f"destination exists but is not a git repo: {dest_dir}\n"
                "delete it (or pick a different workspace) and try again"
            )

    proc: subprocess.CompletedProcess[str]
    if prefer_gh and is_gh_available():
        proc = _run(["gh", "repo", "clone", repo, dest_dir], timeout_s=300.0)
    else:
        proc = subprocess.CompletedProcess(
            args=["gh"], returncode=127, stdout="", stderr="gh not found"
        )
    if proc.returncode != 0:
        proc = _run(["git", "clone", repo, dest_dir], timeout_s=300.0)
    _require_ok(proc, args=["clone", repo, dest_dir])
