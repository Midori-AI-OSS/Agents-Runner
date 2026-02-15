from __future__ import annotations

import os
import socket
import time
from pathlib import Path

import pytest
from PySide6.QtCore import Signal
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from PySide6.QtWidgets import QWidget

from agents_runner.environments import Environment
from agents_runner.environments import WORKSPACE_CLONED
from agents_runner.environments import WORKSPACE_NONE
from agents_runner.ui.pages.tasks import TasksPage

# Keep tests on offscreen by default for regular CI runs.
# If Qt aborts in a headless shell, run under a live X display instead:
# DISPLAY=:1 QT_QPA_PLATFORM=xcb uv run pytest agents_runner/tests/test_tasks_nav_button_fade_behavior.py -q
# or xvfb-run -s "-screen 0 1280x800x24" uv run pytest agents_runner/tests/test_tasks_nav_button_fade_behavior.py -q
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_HEADLESS_SKIP_REASON = (
    "No live X display detected. This Qt test can abort in headless shells. "
    "Run with DISPLAY=:1 QT_QPA_PLATFORM=xcb or with xvfb-run."
)


def _display_socket_path() -> Path | None:
    display = str(os.environ.get("DISPLAY") or "").strip()
    if not display.startswith(":"):
        return None
    display_number = display[1:].split(".", 1)[0]
    if not display_number.isdigit():
        return None
    return Path("/tmp/.X11-unix") / f"X{display_number}"


def _has_live_x_display() -> bool:
    socket_path = _display_socket_path()
    if socket_path is None:
        return False
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(0.2)
            client.connect(str(socket_path))
        return True
    except OSError:
        return False


def _require_live_display() -> None:
    if not _has_live_x_display():
        pytest.skip(_HEADLESS_SKIP_REASON)


class _DummyNewTaskPage(QWidget):
    environment_changed = Signal(str)

    def focus_prompt(self) -> None:
        return

    def set_environment_id(self, _env_id: str) -> None:
        return

    def append_prompt_text(self, _prompt: str) -> None:
        return

    def base_branch_controls_widget(self) -> QWidget:
        return QWidget()

    def set_base_branch_host_active(self, _active: bool) -> None:
        return


def _pump(app: QApplication, rounds: int = 10) -> None:
    for _ in range(rounds):
        app.processEvents()
        QTest.qWait(20)


def _wait_until(
    app: QApplication,
    predicate,
    *,
    timeout_ms: int = 2000,
) -> bool:
    deadline = time.monotonic() + (timeout_ms / 1000)
    while time.monotonic() < deadline:
        app.processEvents()
        if predicate():
            return True
        QTest.qWait(20)
    app.processEvents()
    return bool(predicate())


def _build_envs() -> dict[str, Environment]:
    supported_a = Environment(
        env_id="supported-a",
        name="Supported A",
        color="cyan",
        workspace_type=WORKSPACE_CLONED,
        workspace_target="owner/repo-a",
    )
    supported_b = Environment(
        env_id="supported-b",
        name="Supported B",
        color="emerald",
        workspace_type=WORKSPACE_CLONED,
        workspace_target="owner/repo-b",
    )
    unsupported_a = Environment(
        env_id="unsupported-a",
        name="Unsupported A",
        color="slate",
        workspace_type=WORKSPACE_NONE,
        workspace_target="",
    )
    unsupported_b = Environment(
        env_id="unsupported-b",
        name="Unsupported B",
        color="amber",
        workspace_type=WORKSPACE_NONE,
        workspace_target="",
    )
    return {
        supported_a.env_id: supported_a,
        supported_b.env_id: supported_b,
        unsupported_a.env_id: unsupported_a,
        unsupported_b.env_id: unsupported_b,
    }


def test_tasks_github_buttons_fade_only_on_support_flip() -> None:
    _require_live_display()

    app = QApplication.instance() or QApplication([])

    page = TasksPage(new_task_page=_DummyNewTaskPage())
    page.resize(1400, 900)
    envs = _build_envs()
    page.set_environments(envs, "supported-a")
    page.show()
    _pump(app)

    pull_requests_button = page._nav_buttons["pull_requests"]
    issues_button = page._nav_buttons["issues"]

    assert page._button_fade_animation is None
    assert pull_requests_button.isVisible()
    assert issues_button.isVisible()

    page._new_task.environment_changed.emit("supported-b")
    _pump(app, rounds=6)
    assert page._button_fade_animation is None
    assert pull_requests_button.isVisible()
    assert issues_button.isVisible()

    page._new_task.environment_changed.emit("unsupported-a")
    _pump(app, rounds=2)
    assert page._button_fade_animation is not None
    assert _wait_until(app, lambda: page._button_fade_animation is None)
    assert not pull_requests_button.isVisible()
    assert not issues_button.isVisible()

    page._new_task.environment_changed.emit("unsupported-b")
    _pump(app, rounds=6)
    assert page._button_fade_animation is None
    assert not pull_requests_button.isVisible()
    assert not issues_button.isVisible()

    page._new_task.environment_changed.emit("supported-a")
    _pump(app, rounds=2)
    assert page._button_fade_animation is not None
    assert _wait_until(app, lambda: page._button_fade_animation is None)
    assert pull_requests_button.isVisible()
    assert issues_button.isVisible()


def test_tasks_github_button_fade_ignores_mid_animation_changes() -> None:
    _require_live_display()

    app = QApplication.instance() or QApplication([])

    page = TasksPage(new_task_page=_DummyNewTaskPage())
    page.resize(1400, 900)
    envs = _build_envs()
    page.set_environments(envs, "supported-a")
    page.show()
    _pump(app)

    pull_requests_button = page._nav_buttons["pull_requests"]
    issues_button = page._nav_buttons["issues"]

    page._new_task.environment_changed.emit("unsupported-a")
    _pump(app, rounds=2)
    first_animation = page._button_fade_animation
    assert first_animation is not None

    page._new_task.environment_changed.emit("supported-b")
    _pump(app, rounds=2)
    assert page._button_fade_animation is first_animation

    assert _wait_until(
        app, lambda: page._button_fade_animation is None, timeout_ms=2500
    )
    assert pull_requests_button.isVisible()
    assert issues_button.isVisible()
