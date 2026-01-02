import os
import subprocess

from .errors import GhManagementError


def _noninteractive_env() -> dict[str, str]:
    env = dict(os.environ)
    env.setdefault("GIT_TERMINAL_PROMPT", "0")
    env.setdefault("GCM_INTERACTIVE", "Never")
    env.setdefault("GIT_ASKPASS", "true")
    env.setdefault("SSH_ASKPASS", "true")
    env.setdefault(
        "GIT_SSH_COMMAND",
        "ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new",
    )
    return env


def _run(
    args: list[str],
    *,
    cwd: str | None = None,
    timeout_s: float = 45.0,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            args,
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
            env=_noninteractive_env(),
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired as exc:
        raise GhManagementError(f"command timed out: {' '.join(args)}") from exc
    except OSError as exc:
        raise GhManagementError(f"command failed: {' '.join(args)}") from exc


def _require_ok(proc: subprocess.CompletedProcess[str], *, args: list[str]) -> None:
    if proc.returncode == 0:
        return
    stderr = (proc.stderr or "").strip()
    stdout = (proc.stdout or "").strip()
    extra = stderr or stdout
    if extra:
        raise GhManagementError(f"command failed ({proc.returncode}): {' '.join(args)}\n{extra}")
    raise GhManagementError(f"command failed ({proc.returncode}): {' '.join(args)}")


def _expand_dir(path: str) -> str:
    return os.path.abspath(os.path.expanduser((path or "").strip()))


def _is_empty_dir(path: str) -> bool:
    try:
        return os.path.isdir(path) and not os.listdir(path)
    except OSError:
        return False
