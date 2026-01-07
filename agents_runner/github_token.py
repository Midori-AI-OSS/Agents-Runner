import os
import shutil
import subprocess


def resolve_github_token(
    *, host: str = "github.com", timeout_s: float = 8.0
) -> str | None:
    """Return a GitHub token from the host environment or `gh`, if available.

    Preference order:
      1) `GH_TOKEN`
      2) `GITHUB_TOKEN`
      3) `gh auth token -h <host>`
    """

    for key in ("GH_TOKEN", "GITHUB_TOKEN"):
        value = (os.environ.get(key) or "").strip()
        if value:
            return value

    if shutil.which("gh") is None:
        return None

    try:
        proc = subprocess.run(
            [
                "gh",
                "auth",
                "token",
                "-h",
                str(host or "github.com").strip() or "github.com",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None

    if proc.returncode != 0:
        return None

    raw = (proc.stdout or "").strip()
    if not raw:
        return None
    first = raw.splitlines()[0].strip()
    return first or None
