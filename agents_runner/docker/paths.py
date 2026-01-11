import os
import subprocess


def _is_git_repo_root(path: str) -> bool:
    path = os.path.abspath(os.path.expanduser(str(path or "").strip() or "."))
    if not os.path.isdir(path):
        return False
    try:
        proc = subprocess.run(
            ["git", "-C", path, "rev-parse", "--is-inside-work-tree"],
            check=False,
            capture_output=True,
            text=True,
            timeout=2.0,
            stdin=subprocess.DEVNULL,
        )
    except Exception:
        return False
    return proc.returncode == 0 and (proc.stdout or "").strip().lower() == "true"
