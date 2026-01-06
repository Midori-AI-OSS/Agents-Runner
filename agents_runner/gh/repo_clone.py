import os
import subprocess
import time

from .errors import GhManagementError
from .gh_cli import is_gh_available
from .git_ops import is_git_repo
from .process import _expand_dir, _is_empty_dir, _require_ok, _run


def _normalize_repo_slug(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""

    text = value
    if text.startswith("git@github.com:"):
        text = text.removeprefix("git@github.com:").strip()
    elif "github.com/" in text:
        text = text.split("github.com/", 1)[-1].strip()
    elif "://" not in text and "/" in text and " " not in text:
        text = text
    else:
        return ""

    text = text.split("#", 1)[0].split("?", 1)[0].strip().strip("/")
    if text.endswith(".git"):
        text = text[: -len(".git")].strip().strip("/")
    parts = [p for p in text.split("/") if p]
    if len(parts) < 2:
        return ""
    return f"{parts[-2].lower()}/{parts[-1].lower()}"


def _read_origin_url(dest_dir: str) -> str:
    dest_dir = _expand_dir(dest_dir)
    git_path = os.path.join(dest_dir, ".git")
    git_dir = ""
    if os.path.isdir(git_path):
        git_dir = git_path
    elif os.path.isfile(git_path):
        try:
            with open(git_path, "r", encoding="utf-8") as f:
                raw = (f.read() or "").strip()
        except Exception:
            raw = ""
        if raw.startswith("gitdir:"):
            candidate = raw.split(":", 1)[-1].strip()
            if candidate:
                candidate = (
                    candidate
                    if os.path.isabs(candidate)
                    else os.path.normpath(os.path.join(dest_dir, candidate))
                )
                if os.path.isdir(candidate):
                    git_dir = candidate
    if not git_dir:
        return ""

    config_path = os.path.join(git_dir, "config")
    if not os.path.isfile(config_path):
        return ""

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            lines = (f.read() or "").splitlines()
    except Exception:
        return ""

    in_origin = False
    for raw in lines:
        line = (raw or "").strip()
        if not line or line.startswith(("#", ";")):
            continue
        if line.startswith("[") and line.endswith("]"):
            in_origin = line.lower() == '[remote "origin"]'
            continue
        if not in_origin:
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip().lower() == "url":
            return value.strip()
    return ""


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
            desired = _normalize_repo_slug(repo)
            existing = _normalize_repo_slug(_read_origin_url(dest_dir))
            if desired and existing and desired != existing:
                if recreate_if_needed and os.path.isdir(dest_dir):
                    backup_dir = f"{dest_dir}.bak-{time.time_ns()}"
                    try:
                        os.replace(dest_dir, backup_dir)
                    except OSError as exc:
                        raise GhManagementError(
                            f"destination contains a different repo ({existing}), expected {desired}: {dest_dir}\n"
                            f"failed to move it aside to {backup_dir}: {exc}"
                        ) from exc
                else:
                    raise GhManagementError(
                        f"destination contains a different repo ({existing}), expected {desired}: {dest_dir}\n"
                        "delete it (or pick a different workspace) and try again"
                    )
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
