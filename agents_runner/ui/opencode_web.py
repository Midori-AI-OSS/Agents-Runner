from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from agents_runner.ui.main_window import MainWindow

import random
import socket
import time
import urllib.error
import urllib.request

from PySide6.QtCore import QTimer

from agents_runner.log_format import format_log
from agents_runner.ui.url_open import open_external_url

OPENCODE_WEB_CONTAINER_PORT = 4096
OPENCODE_WEB_ALT_CONTAINER_PORT_MIN = 20_000
OPENCODE_WEB_ALT_CONTAINER_PORT_MAX = 60_999
OPENCODE_WEB_HOST = "127.0.0.1"
OPENCODE_WEB_RETRY_INTERVAL_MS = 500
OPENCODE_WEB_TIMEOUT_MS = 10 * 60 * 1000
OPENCODE_WEB_HTTP_TIMEOUT_S = 0.75


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
    main_window: MainWindow,
    task_id: str,
    url: str,
    host_port: int,
) -> None:
    state = {"done": False}
    deadline_s = time.monotonic() + (OPENCODE_WEB_TIMEOUT_MS / 1000.0)
    readiness_url = f"http://{OPENCODE_WEB_HOST}:{int(host_port)}/"
    main_window._on_task_log(
        task_id,
        format_log(
            "opencode",
            "web",
            "INFO",
            f"waiting for HTTP readiness: {readiness_url}",
        ),
    )

    def _attempt_open() -> None:
        if bool(state.get("done", False)):
            return
        status_code = _http_status_code(readiness_url)
        if status_code is not None:
            state["done"] = True
            main_window._on_task_log(
                task_id,
                format_log(
                    "opencode",
                    "web",
                    "INFO",
                    f"HTTP readiness returned {status_code}: {readiness_url}",
                ),
            )
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
                    f"web server never returned an HTTP status after 10 minutes; stopped browser open retry: {url}",
                ),
            )
            return

        QTimer.singleShot(OPENCODE_WEB_RETRY_INTERVAL_MS, _attempt_open)

    _attempt_open()


def _port_specs_publish_container_port(port_specs: list[str], port: int) -> bool:
    return any(publishes_container_port(spec, port) for spec in port_specs)


def _http_status_code(url: str) -> int | None:
    request = urllib.request.Request(
        str(url),
        method="GET",
        headers={"User-Agent": "agents-runner-opencode-readiness"},
    )
    try:
        with urllib.request.urlopen(  # noqa: S310
            request,
            timeout=OPENCODE_WEB_HTTP_TIMEOUT_S,
        ) as response:
            status = int(response.status)
    except urllib.error.HTTPError as exc:
        status = int(exc.code)
    except (OSError, ValueError):
        return None

    if 100 <= status <= 599:
        return status
    return None
