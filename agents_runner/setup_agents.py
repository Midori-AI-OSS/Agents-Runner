from __future__ import annotations

import hashlib
import os
import stat
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from agents_runner.environments.paths import default_data_dir, managed_repos_dir
from agents_runner.gh.git_ops import git_repo_root, is_git_repo
from agents_runner.log_format import format_log

SETUP_AGENTS_PRIMARY_RELATIVE_PATH = ".agents/setup-agents.sh"
SETUP_AGENTS_FALLBACK_RELATIVE_PATH = ".github/setup-agents.sh"


@dataclass(frozen=True)
class SetupAgentsResult:
    repo_root: str
    repo_script_path: str | None
    mirror_script_path: str
    setup_script: str | None
    source: str
    created_from_legacy: bool
    committed_legacy_bootstrap: bool
    prompt_instruction: str | None


def _safe_segment(value: str, fallback: str = "default") -> str:
    safe = "".join(ch for ch in str(value or "").strip() if ch.isalnum() or ch in "-_")
    return safe or fallback


def _normalize_repo_slug(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
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
    parts = [part for part in text.split("/") if part]
    if len(parts) < 2:
        return ""
    return f"{parts[-2].lower()}/{parts[-1].lower()}"


def _repo_key(*, repo_root: Path, gh_repo: str | None) -> str:
    slug = _normalize_repo_slug(str(gh_repo or ""))
    if slug:
        return slug.replace("/", "__")
    digest = hashlib.sha1(str(repo_root).encode("utf-8")).hexdigest()[:12]
    return f"{_safe_segment(repo_root.name, fallback='repo')}__{digest}"


def _resolve_repo_root(host_workdir: str) -> Path:
    host = os.path.abspath(os.path.expanduser(str(host_workdir or "").strip()))
    if not host:
        return Path.cwd()
    detected = git_repo_root(host)
    if detected:
        return Path(detected).resolve()
    return Path(host).resolve()


def _normalize_script_text(text: str) -> str:
    normalized = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    if normalized and not normalized.endswith("\n"):
        normalized += "\n"
    return normalized


def _is_executable(path: Path) -> bool:
    try:
        return bool(path.stat().st_mode & stat.S_IXUSR)
    except OSError:
        return False


def _write_script(path: Path, text: str, *, executable: bool) -> bool:
    normalized = _normalize_script_text(text)
    current_text = ""
    current_exec = False
    if path.is_file():
        try:
            current_text = _normalize_script_text(path.read_text(encoding="utf-8"))
            current_exec = _is_executable(path)
        except Exception:
            current_text = ""
            current_exec = False
    if path.is_file() and current_text == normalized and current_exec == executable:
        return False

    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix="setup-agents-", suffix=".sh")
    tmp_file = Path(tmp_path)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(normalized)
        os.replace(tmp_file, path)
    finally:
        try:
            if tmp_file.exists():
                tmp_file.unlink()
        except OSError:
            pass

    mode = 0o755 if executable else 0o644
    os.chmod(path, mode)
    return True


def _copy_script(source: Path, destination: Path) -> bool:
    text = source.read_text(encoding="utf-8")
    return _write_script(destination, text, executable=_is_executable(source))


def _git_last_commit_timestamp(repo_root: Path, script_path: Path) -> float:
    try:
        rel_path = str(script_path.relative_to(repo_root))
    except ValueError:
        return 0.0
    proc = subprocess.run(
        ["git", "-C", str(repo_root), "log", "-1", "--format=%ct", "--", rel_path],
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return 0.0
    output = str(proc.stdout or "").strip()
    if not output.isdigit():
        return 0.0
    return float(output)


def _repo_script_timestamp(repo_root: Path, script_path: Path) -> float:
    try:
        mtime = script_path.stat().st_mtime
    except OSError:
        return 0.0
    if not is_git_repo(str(repo_root)):
        return mtime
    return max(mtime, _git_last_commit_timestamp(repo_root, script_path))


def _commit_bootstrap_script(repo_root: Path, script_path: Path) -> bool:
    try:
        rel = str(script_path.relative_to(repo_root))
    except ValueError:
        return False

    add_proc = subprocess.run(
        ["git", "-C", str(repo_root), "add", "--", rel],
        check=False,
        capture_output=True,
        text=True,
    )
    if add_proc.returncode != 0:
        return False

    staged_proc = subprocess.run(
        ["git", "-C", str(repo_root), "diff", "--cached", "--quiet", "--", rel],
        check=False,
        capture_output=True,
        text=True,
    )
    if staged_proc.returncode == 0:
        return False

    commit_proc = subprocess.run(
        [
            "git",
            "-C",
            str(repo_root),
            "commit",
            "-m",
            "[CHORE] Bootstrap setup-agents.sh from legacy preflight",
            "--",
            rel,
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    return commit_proc.returncode == 0


def _missing_instruction() -> str:
    return (
        "Repository bootstrap is missing. Create `.agents/setup-agents.sh` "
        "(or `.github/setup-agents.sh`), make it executable, add your setup steps, "
        "then commit the file to the repository."
    )


def prepare_setup_agents_phase(
    *,
    host_workdir: str,
    environment_id: str,
    gh_repo: str | None = None,
    data_dir: str | None = None,
    legacy_environment_preflight_script: str | None = None,
    launch_mode: str = "agent",
    on_log: Callable[[str], None] | None = None,
) -> SetupAgentsResult:
    def _log(level: str, message: str) -> None:
        if on_log is None:
            return
        on_log(format_log("setup", "agents", level, message))

    repo_root = _resolve_repo_root(host_workdir)
    primary = repo_root / SETUP_AGENTS_PRIMARY_RELATIVE_PATH
    fallback = repo_root / SETUP_AGENTS_FALLBACK_RELATIVE_PATH

    repo_script_path: Path | None = None
    if primary.is_file():
        repo_script_path = primary
    elif fallback.is_file():
        repo_script_path = fallback

    selected_repo_path = repo_script_path or primary

    base_dir = Path(managed_repos_dir(data_dir or default_data_dir()))
    mirror_path = (
        base_dir
        / _safe_segment(environment_id)
        / "metadata"
        / "setup-agents"
        / _repo_key(repo_root=repo_root, gh_repo=gh_repo)
        / "setup-agents.sh"
    )

    source = "none"
    created_from_legacy = False
    committed_legacy_bootstrap = False

    legacy_script = _normalize_script_text(
        str(legacy_environment_preflight_script or "")
    )
    legacy_available = bool(legacy_script.strip())
    mirror_exists = mirror_path.is_file()

    if repo_script_path is None and not mirror_exists and legacy_available:
        if _write_script(selected_repo_path, legacy_script, executable=True):
            created_from_legacy = True
            source = "legacy"
            _log(
                "INFO",
                f"created {selected_repo_path} from legacy environment preflight",
            )
        repo_script_path = selected_repo_path
        if is_git_repo(str(repo_root)):
            committed_legacy_bootstrap = _commit_bootstrap_script(
                repo_root, repo_script_path
            )
            if committed_legacy_bootstrap:
                _log(
                    "INFO",
                    f"committed bootstrap script to repository at {repo_script_path}",
                )
            else:
                _log(
                    "WARN",
                    f"auto-commit failed for bootstrap script at {repo_script_path}",
                )

    if repo_script_path is not None and mirror_path.is_file():
        repo_ts = _repo_script_timestamp(repo_root, repo_script_path)
        mirror_ts = mirror_path.stat().st_mtime
        if repo_ts >= mirror_ts:
            if _copy_script(repo_script_path, mirror_path):
                _log(
                    "INFO",
                    f"sync repo -> mirror ({repo_script_path} -> {mirror_path})",
                )
            if source == "none":
                source = "repo"
        else:
            if _copy_script(mirror_path, repo_script_path):
                _log(
                    "INFO",
                    f"sync mirror -> repo ({mirror_path} -> {repo_script_path})",
                )
            source = "mirror"
    elif repo_script_path is not None:
        if _copy_script(repo_script_path, mirror_path):
            _log(
                "INFO",
                f"sync repo -> mirror ({repo_script_path} -> {mirror_path})",
            )
        if source == "none":
            source = "repo"
    elif mirror_path.is_file():
        _log(
            "INFO",
            (
                "repo setup script missing; skipping mirror restore "
                "(repo delete authority is active)"
            ),
        )

    setup_script: str | None = None
    if repo_script_path is not None and repo_script_path.is_file():
        try:
            setup_script = _normalize_script_text(
                repo_script_path.read_text(encoding="utf-8")
            )
        except Exception as exc:
            _log(
                "WARN",
                f"failed to read setup-agents script at {repo_script_path}: {exc}",
            )
            setup_script = None

    launch_mode_normalized = str(launch_mode or "agent").strip().lower()
    prompt_instruction = None
    if not setup_script and launch_mode_normalized != "ide":
        prompt_instruction = _missing_instruction()
        _log("INFO", "setup-agents script not found; prompt guidance will be injected")

    return SetupAgentsResult(
        repo_root=str(repo_root),
        repo_script_path=str(repo_script_path) if repo_script_path else None,
        mirror_script_path=str(mirror_path),
        setup_script=setup_script,
        source=source,
        created_from_legacy=created_from_legacy,
        committed_legacy_bootstrap=committed_legacy_bootstrap,
        prompt_instruction=prompt_instruction,
    )
