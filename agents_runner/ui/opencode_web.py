from __future__ import annotations

import random
import socket
import time

from PySide6.QtCore import QTimer

from agents_runner.log_format import format_log
from agents_runner.ui.url_open import open_external_url

OPENCODE_WEB_CONTAINER_PORT = 4096
OPENCODE_WEB_ALT_CONTAINER_PORT_MIN = 20_000
OPENCODE_WEB_ALT_CONTAINER_PORT_MAX = 60_999
OPENCODE_WEB_HOST = "127.0.0.1"
OPENCODE_WEB_RETRY_INTERVAL_MS = 15_000
OPENCODE_WEB_TIMEOUT_MS = 10 * 60 * 1000


def publishes_container_port(spec: str, port: int) -> bool:
    base = str(spec or "").strip()
    if not base:
        return False
    base = base.split("/", 1)[0]
    container_part = base.rsplit(":", 1)[-1].strip()
    if not container_part:
        return False
    if container_part.isdigit():
        return int(container_part) == int(port)
    if "-" in container_part:
        left, right = (p.strip() for p in container_part.split("-", 1))
        if left.isdigit() and right.isdigit():
            start = int(left)
            end = int(right)
            p = int(port)
            return start <= p <= end
    return False


def select_opencode_web_container_port(port_specs: list[str]) -> int:
    if not _port_specs_publish_container_port(port_specs, OPENCODE_WEB_CONTAINER_PORT):
        return OPENCODE_WEB_CONTAINER_PORT

    for _ in range(128):
        candidate = random.randint(
            OPENCODE_WEB_ALT_CONTAINER_PORT_MIN,
            OPENCODE_WEB_ALT_CONTAINER_PORT_MAX,
        )
        if not _port_specs_publish_container_port(port_specs, candidate):
            return candidate

    for candidate in range(
        OPENCODE_WEB_ALT_CONTAINER_PORT_MIN,
        OPENCODE_WEB_ALT_CONTAINER_PORT_MAX + 1,
    ):
        if not _port_specs_publish_container_port(port_specs, candidate):
            return candidate

    raise RuntimeError("Could not find an unused container port for OpenCode Web.")


def allocate_localhost_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((OPENCODE_WEB_HOST, 0))
        return int(sock.getsockname()[1])


def schedule_open_opencode_web_url(
    *,
    main_window: object,
    task_id: str,
    url: str,
    host_port: int,
) -> None:
    state = {"done": False}
    deadline_s = time.monotonic() + (OPENCODE_WEB_TIMEOUT_MS / 1000.0)

    def _attempt_open() -> None:
        if bool(state.get("done", False)):
            return
        if _can_connect_to_local_port(host_port):
            state["done"] = True
            opened = open_external_url(url)
            log_level = "INFO" if opened else "WARN"
            log_message = (
                f"opened browser: {url}"
                if opened
                else f"web server is ready but host opener did not report success: {url}"
            )
            main_window._on_task_log(
                task_id,
                format_log("opencode", "web", log_level, log_message),
            )
            return

        if time.monotonic() >= deadline_s:
            state["done"] = True
            main_window._on_task_log(
                task_id,
                format_log(
                    "opencode",
                    "web",
                    "WARN",
                    "web server was not ready after 10 minutes; "
                    f"stopped browser open retry: {url}",
                ),
            )
            return

        QTimer.singleShot(OPENCODE_WEB_RETRY_INTERVAL_MS, _attempt_open)

    _attempt_open()


def _port_specs_publish_container_port(port_specs: list[str], port: int) -> bool:
    return any(publishes_container_port(spec, port) for spec in port_specs)


def _can_connect_to_local_port(port: int) -> bool:
    try:
        with socket.create_connection((OPENCODE_WEB_HOST, int(port)), timeout=0.25):
            return True
    except OSError:
        return False
