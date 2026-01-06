import json
import subprocess

from typing import Any


def _run_docker(
    args: list[str], timeout_s: float = 30.0, *, env: dict[str, str] | None = None
) -> str:
    completed = subprocess.run(
        ["docker", *args],
        capture_output=True,
        check=False,
        env=env,
        text=True,
        timeout=timeout_s,
    )
    if completed.returncode != 0:
        stderr = (completed.stderr or "").strip()
        stdout = (completed.stdout or "").strip()
        detail = stderr or stdout or f"docker exited {completed.returncode}"
        raise RuntimeError(detail)
    return (completed.stdout or "").strip()


def _inspect_state(container_id: str) -> dict[str, Any]:
    """Get container state from docker inspect."""
    raw = _run_docker(["inspect", container_id], timeout_s=30.0)
    payload = json.loads(raw)
    return payload[0].get("State", {}) if payload else {}


def _has_image(image: str) -> bool:
    try:
        _run_docker(["image", "inspect", image], timeout_s=10.0)
        return True
    except Exception:
        return False


def _has_platform_image(image: str, platform_value: str) -> bool:
    platform_value = str(platform_value or "").strip()
    try:
        expected_arch = platform_value.split("/")[1].strip().lower()
    except Exception:
        expected_arch = ""
    if not expected_arch:
        return _has_image(image)

    try:
        actual_arch = (
            _run_docker(
                ["image", "inspect", image, "--format", "{{.Architecture}}"],
                timeout_s=10.0,
            )
            .strip()
            .lower()
        )
    except Exception:
        return False
    return actual_arch == expected_arch


def _pull_image(image: str, *, platform_args: list[str]) -> None:
    _run_docker(["pull", *list(platform_args or []), image], timeout_s=600.0)
