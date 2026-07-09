import io
import json
import selectors
import subprocess
import time
from collections.abc import Callable
from typing import Any
from typing import cast


def run_docker(args: list[str], timeout_s: float = 30.0, *, env: dict[str, str] | None = None) -> str:
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


def inspect_state(container_id: str) -> dict[str, Any]:
    """Get container state from docker inspect."""
    raw = run_docker(["inspect", container_id], timeout_s=30.0)
    payload = json.loads(raw)
    return payload[0].get("State", {}) if payload else {}


def has_image(image: str) -> bool:
    try:
        run_docker(["image", "inspect", image], timeout_s=10.0)
        return True
    except Exception:
        return False


def has_platform_image(image: str, platform_value: str) -> bool:
    platform_value = str(platform_value or "").strip()
    try:
        expected_arch = platform_value.split("/")[1].strip().lower()
    except Exception:
        expected_arch = ""
    if not expected_arch:
        return has_image(image)

    try:
        actual_arch = (
            run_docker(
                ["image", "inspect", image, "--format", "{{.Architecture}}"],
                timeout_s=10.0,
            )
            .strip()
            .lower()
        )
    except Exception:
        return False
    return actual_arch == expected_arch


def pull_image(
    image: str,
    *,
    platform_args: list[str] | None = None,
    on_log: Callable[[str], None] | None = None,
    check_stop: Callable[[], bool] | None = None,
    timeout_s: float = 600.0,
) -> None:
    cmd = ["docker", "pull", *(platform_args or []), image]
    start_s = time.monotonic()
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    if proc.stdout is None:
        raise RuntimeError("docker pull: failed to open stdout pipe")
    sel = selectors.DefaultSelector()
    sel.register(proc.stdout, selectors.EVENT_READ)
    try:
        while True:
            elapsed = time.monotonic() - start_s
            if elapsed > timeout_s:
                if proc.poll() is not None:
                    break
                proc.kill()
                try:
                    proc.wait(timeout=5.0)
                except subprocess.TimeoutExpired:
                    pass
                raise TimeoutError(f"docker pull timed out after {timeout_s:.0f}s: {image}")
            if check_stop is not None and check_stop():
                proc.kill()
                try:
                    proc.wait(timeout=5.0)
                except subprocess.TimeoutExpired:
                    pass
                raise RuntimeError("docker pull cancelled")
            ready = sel.select(timeout=0.1)
            for key, _mask in ready:
                line = cast(io.TextIOBase, key.fileobj).readline()
                if line:
                    if on_log is not None:
                        on_log(line.rstrip("\n"))
                else:
                    break
            if proc.poll() is not None:
                for key, _mask in sel.select(timeout=0):
                    remaining = cast(io.TextIOBase, key.fileobj).read()
                    if remaining and on_log is not None:
                        for rline in remaining.splitlines():
                            on_log(rline)
                break
    finally:
        sel.close()
    if proc.returncode != 0:
        raise RuntimeError(f"docker pull failed with exit code {proc.returncode}: {image}")
