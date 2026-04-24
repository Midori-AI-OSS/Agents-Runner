from __future__ import annotations

import hashlib
import os
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from agents_runner.environments.preflight_snapshot import (
    build_preflight_identity_token,
    decrypt_setup_agents_snapshot,
    encrypt_setup_agents_snapshot,
)
from agents_runner.gh.git_ops import git_repo_root, normalize_github_repo_slug
from agents_runner.log_format import format_log

SETUP_AGENTS_PRIMARY_RELATIVE_PATH = ".agents/setup-agents.sh"
SETUP_AGENTS_FALLBACK_RELATIVE_PATH = ".github/setup-agents.sh"
SETUP_AGENTS_MIRROR_ENCRYPTED_PREFIX = "midori-setup-agents:v1:"


@dataclass(frozen=True)
class SetupAgentsResult:
    repo_root: str
    repo_script_path: str | None
    mirror_script_path: str
    setup_script: str | None
    source: str
    prompt_instruction: str | None


@dataclass(frozen=True)
class SetupAgentsPreviewResult:
    repo_root: str
    repo_script_path: str | None
    preferred_repo_script_path: str
    mirror_script_path: str
    effective_script_path: str | None
    setup_script: str | None
    source: str
    guidance: str
    error: str | None


def missing_setup_agents_instruction(*, launch_mode: str) -> str | None:
    launch_mode_normalized = str(launch_mode or "agent").strip().lower()
    if launch_mode_normalized == "ide":
        return None
    return _missing_instruction()


def _safe_segment(value: str, fallback: str = "default") -> str:
    safe = "".join(ch for ch in str(value or "").strip() if ch.isalnum() or ch in "-_")
    return safe or fallback


def _repo_key(*, repo_root: Path, gh_repo: str | None) -> str:
    slug = normalize_github_repo_slug(str(gh_repo or ""))
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
    fd, tmp_path = tempfile.mkstemp(
        prefix="setup-agents-", suffix=".sh", dir=str(path.parent)
    )
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


def _missing_instruction() -> str:
    return (
        "Repository bootstrap is missing. Create `.agents/setup-agents.sh`, "
        "make it executable, and commit it. `setup-agents.sh` is always executed "
        "from the repository root (do NOT add cd commands). The script must only "
        "prepare/setup the agent container so it is ready for use; do not perform "
        "repository setup. Environment is PixelArch: package installs must use "
        "`yay -Syu` only; never `pacman`; never plain `yay -S`."
    )


def _setup_agents_metadata_root() -> Path:
    # Keep setup-agents metadata outside managed repo checkouts.
    return Path.home() / ".midoriai" / "agents-runner" / "metadata-repos"


def _resolve_repo_and_mirror_paths(
    *,
    host_workdir: str,
    environment_id: str,
    gh_repo: str | None,
    data_dir: str | None,
) -> tuple[Path, Path, Path, Path, Path]:
    _ = data_dir
    repo_root = _resolve_repo_root(host_workdir)
    primary = repo_root / SETUP_AGENTS_PRIMARY_RELATIVE_PATH
    fallback = repo_root / SETUP_AGENTS_FALLBACK_RELATIVE_PATH

    repo_script_path: Path | None = None
    if primary.is_file():
        repo_script_path = primary
    elif fallback.is_file():
        repo_script_path = fallback

    selected_repo_path = repo_script_path or primary

    base_dir = _setup_agents_metadata_root()
    mirror_path = (
        base_dir
        / _safe_segment(environment_id)
        / "setup-agents"
        / _repo_key(repo_root=repo_root, gh_repo=gh_repo)
        / "setup-agents.sh"
    )
    return repo_root, primary, fallback, mirror_path, selected_repo_path


def _read_script(path: Path) -> tuple[str | None, str | None]:
    try:
        return _normalize_script_text(path.read_text(encoding="utf-8")), None
    except Exception as exc:
        return None, str(exc)


def _preflight_identity_token(
    *,
    environment_id: str,
    workspace_type: str,
    workspace_target: str,
    host_workdir: str,
) -> str:
    return build_preflight_identity_token(
        env_id=environment_id,
        workspace_type=workspace_type,
        workspace_target=workspace_target,
        host_workdir=host_workdir,
    )


def _encode_encrypted_mirror_payload(ciphertext: str) -> str:
    token = str(ciphertext or "").strip()
    return f"{SETUP_AGENTS_MIRROR_ENCRYPTED_PREFIX}{token}\n"


def _read_mirror_script(
    *,
    mirror_path: Path,
    environment_id: str,
    workspace_type: str,
    workspace_target: str,
    host_workdir: str,
) -> tuple[str | None, str | None]:
    try:
        payload = mirror_path.read_text(encoding="utf-8")
    except Exception as exc:
        return None, str(exc)

    marker = SETUP_AGENTS_MIRROR_ENCRYPTED_PREFIX
    stripped = str(payload or "").strip()
    if not stripped:
        return "", None
    if not stripped.startswith(marker):
        # Backward compatibility: legacy plaintext mirrors are accepted read-only.
        return _normalize_script_text(payload), None

    ciphertext = stripped.removeprefix(marker).strip()
    if not ciphertext:
        return None, "encrypted mirror payload is missing ciphertext"

    identity_token = _preflight_identity_token(
        environment_id=environment_id,
        workspace_type=workspace_type,
        workspace_target=workspace_target,
        host_workdir=host_workdir,
    )
    plaintext = decrypt_setup_agents_snapshot(
        env_id=environment_id,
        identity_token=identity_token,
        ciphertext=ciphertext,
    )
    if plaintext is None:
        return (
            None,
            "encrypted mirror payload could not be decrypted for current workspace identity",
        )
    return _normalize_script_text(plaintext), None


def _write_encrypted_mirror_script(
    *,
    mirror_path: Path,
    plaintext_script: str,
    environment_id: str,
    workspace_type: str,
    workspace_target: str,
    host_workdir: str,
) -> bool:
    identity_token = _preflight_identity_token(
        environment_id=environment_id,
        workspace_type=workspace_type,
        workspace_target=workspace_target,
        host_workdir=host_workdir,
    )
    ciphertext, _ = encrypt_setup_agents_snapshot(
        env_id=environment_id,
        identity_token=identity_token,
        plaintext=plaintext_script,
    )
    return _write_script(
        mirror_path,
        _encode_encrypted_mirror_payload(ciphertext),
        executable=False,
    )


def _path_relative_to_repo(*, repo_root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(repo_root))
    except ValueError:
        return str(path)


def resolve_setup_agents_preview(
    *,
    host_workdir: str,
    environment_id: str,
    workspace_type: str = "",
    workspace_target: str = "",
    gh_repo: str | None = None,
    data_dir: str | None = None,
) -> SetupAgentsPreviewResult:
    repo_root, primary, fallback, mirror_path, selected_repo_path = (
        _resolve_repo_and_mirror_paths(
            host_workdir=host_workdir,
            environment_id=environment_id,
            gh_repo=gh_repo,
            data_dir=data_dir,
        )
    )
    repo_script_path: Path | None = None
    if primary.is_file():
        repo_script_path = primary
    elif fallback.is_file():
        repo_script_path = fallback

    preferred_repo_path = selected_repo_path
    source = "none"
    effective_script_path: Path | None = None
    setup_script: str | None = None
    read_error: str | None = None

    mirror_exists = mirror_path.is_file()
    if repo_script_path is not None:
        source = "repo"
        effective_script_path = repo_script_path
        setup_script, script_error = _read_script(repo_script_path)
        if script_error:
            read_error = (
                f"failed to read setup-agents script at {repo_script_path}: "
                f"{script_error}"
            )
            if mirror_exists:
                mirror_script, mirror_error = _read_mirror_script(
                    mirror_path=mirror_path,
                    environment_id=environment_id,
                    workspace_type=workspace_type,
                    workspace_target=workspace_target,
                    host_workdir=host_workdir,
                )
                if mirror_error:
                    read_error = f"{read_error}; mirror fallback failed: {mirror_error}"
                else:
                    source = "mirror"
                    effective_script_path = mirror_path
                    setup_script = mirror_script
    elif mirror_exists:
        source = "mirror"
        effective_script_path = mirror_path
        setup_script, script_error = _read_mirror_script(
            mirror_path=mirror_path,
            environment_id=environment_id,
            workspace_type=workspace_type,
            workspace_target=workspace_target,
            host_workdir=host_workdir,
        )
        if script_error:
            read_error = (
                f"failed to read setup-agents mirror at {mirror_path}: {script_error}"
            )

    preferred_rel = _path_relative_to_repo(
        repo_root=repo_root, path=preferred_repo_path
    )
    guidance = (
        "This script preview is read-only. "
        f"Edit `{preferred_rel}` in your repository and commit the change."
    )
    if source == "none":
        guidance = (
            "setup-agents script is missing. "
            f"Create `{preferred_rel}` in your repository, make it executable, and commit it."
        )

    return SetupAgentsPreviewResult(
        repo_root=str(repo_root),
        repo_script_path=str(repo_script_path) if repo_script_path else None,
        preferred_repo_script_path=str(preferred_repo_path),
        mirror_script_path=str(mirror_path),
        effective_script_path=str(effective_script_path)
        if effective_script_path
        else None,
        setup_script=setup_script,
        source=source,
        guidance=guidance,
        error=read_error,
    )


def prepare_setup_agents_phase(
    *,
    host_workdir: str,
    environment_id: str,
    workspace_type: str = "",
    workspace_target: str = "",
    gh_repo: str | None = None,
    data_dir: str | None = None,
    launch_mode: str = "agent",
    on_log: Callable[[str], None] | None = None,
) -> SetupAgentsResult:
    def _log(level: str, message: str) -> None:
        if on_log is None:
            return
        on_log(format_log("setup", "agents", level, message))

    repo_root, primary, fallback, mirror_path, _ = _resolve_repo_and_mirror_paths(
        host_workdir=host_workdir,
        environment_id=environment_id,
        gh_repo=gh_repo,
        data_dir=data_dir,
    )
    repo_script_path: Path | None = None
    if primary.is_file():
        repo_script_path = primary
    elif fallback.is_file():
        repo_script_path = fallback
    source = "none"

    try:
        mirror_exists = mirror_path.is_file()
    except Exception as exc:
        _log("WARN", f"failed to inspect setup-agents mirror path {mirror_path}: {exc}")
        mirror_exists = False

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
        else:
            source = "repo"
            try:
                changed = _write_encrypted_mirror_script(
                    mirror_path=mirror_path,
                    plaintext_script=setup_script,
                    environment_id=environment_id,
                    workspace_type=workspace_type,
                    workspace_target=workspace_target,
                    host_workdir=host_workdir,
                )
            except Exception as exc:
                _log(
                    "WARN",
                    f"sync repo -> mirror failed ({repo_script_path} -> {mirror_path}): {exc}",
                )
            else:
                if changed:
                    _log(
                        "INFO",
                        f"sync repo -> mirror ({repo_script_path} -> {mirror_path})",
                    )
    elif mirror_exists:
        _log(
            "INFO",
            (
                "repo setup script missing; skipping mirror restore "
                "(repo delete authority is active)"
            ),
        )

    prompt_instruction = None
    if not setup_script:
        prompt_instruction = missing_setup_agents_instruction(launch_mode=launch_mode)
        if prompt_instruction:
            _log(
                "INFO",
                "setup-agents script not found; prompt guidance will be injected",
            )

    return SetupAgentsResult(
        repo_root=str(repo_root),
        repo_script_path=str(repo_script_path) if repo_script_path else None,
        mirror_script_path=str(mirror_path),
        setup_script=setup_script,
        source=source,
        prompt_instruction=prompt_instruction,
    )
