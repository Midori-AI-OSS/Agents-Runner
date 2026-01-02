from __future__ import annotations

import shlex
import shutil
import subprocess
import threading

from collections.abc import Callable


def _format_cmd(args: list[str]) -> str:
    return " ".join(shlex.quote(str(a)) for a in args)


def _stream_cmd(
    args: list[str],
    log: Callable[[str], None],
    stop: threading.Event,
    *,
    timeout_s: float = 120.0,
) -> tuple[int, list[str]]:
    log(f"$ {_format_cmd(args)}")
    output_lines: list[str] = []
    try:
        proc = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
    except Exception as exc:
        return 1, [str(exc)]
    assert proc.stdout is not None
    for raw in proc.stdout:
        if stop.is_set():
            try:
                proc.terminate()
            except Exception:
                pass
            break
        line = str(raw or "").rstrip("\n")
        if line:
            log(line)
            output_lines.append(line)
    try:
        exit_code = int(proc.wait(timeout=timeout_s))
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass
        exit_code = 1
    return exit_code, output_lines


def run_docker_cleanup(
    log: Callable[[str], None],
    stop: threading.Event,
) -> tuple[int, str]:
    steps: list[tuple[str, list[str]]] = [
        ("Pruning containers", ["docker", "container", "prune", "-f"]),
        ("Pruning images", ["docker", "image", "prune", "-a", "-f"]),
        ("Pruning volumes", ["docker", "volume", "prune", "-f"]),
        ("Pruning networks", ["docker", "network", "prune", "-f"]),
        ("Final system prune", ["docker", "system", "prune", "-f", "-a"]),
    ]

    all_output: list[str] = []
    sudo = shutil.which("sudo") is not None
    for label, docker_args in steps:
        if stop.is_set():
            msg = "Cancelled."
            log(msg)
            return 1, msg
        args = ["sudo", "-n", *docker_args] if sudo else docker_args
        log(f"[docker] {label}…")
        exit_code, lines = _stream_cmd(args, log, stop)
        all_output.extend(lines)
        if exit_code != 0:
            msg = f"Step failed ({label}); exit code {exit_code}."
            log(msg)
            all_output.append(msg)
            output = "\n".join(all_output).strip() or msg
            return int(exit_code), output

    output = "\n".join(all_output).strip()
    if not output:
        output = "Docker cleanup completed."
    return 0, output

