# pyright: reportPrivateUsage=false
from __future__ import annotations

import time
from collections.abc import Callable

from PySide6.QtCore import QCoreApplication
from PySide6.QtTest import QTest

import pytest

from agents_runner.environments import Environment
from agents_runner.environments import WORKSPACE_CLONED
from agents_runner.ui.pages.github_work_coordinator import GitHubWorkCoordinator


def _app() -> QCoreApplication:
    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication([])
    return app


def _wait_until(
    predicate: Callable[[], bool],
    *,
    timeout_ms: int = 2000,
) -> bool:
    app = _app()
    deadline = time.monotonic() + (timeout_ms / 1000.0)
    while time.monotonic() < deadline:
        app.processEvents()
        if predicate():
            return True
        QTest.qWait(10)
    app.processEvents()
    return bool(predicate())


def test_polling_starts_immediately_when_startup_delay_is_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _app()
    coordinator = GitHubWorkCoordinator()

    start_calls = 0

    def _record_start() -> None:
        nonlocal start_calls
        start_calls += 1

    monkeypatch.setattr(coordinator, "_start_poll_cycle", _record_start)

    coordinator.set_settings_data(
        {
            "github_polling_enabled": True,
            "github_poll_interval_s": 30,
            "github_poll_startup_delay_s": 0,
        }
    )

    assert start_calls == 1
    assert coordinator._startup_poll_started is True
    assert coordinator._poll_timer.isActive()

    coordinator.set_settings_data({"github_polling_enabled": False})


def test_polling_starts_after_startup_delay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _app()
    coordinator = GitHubWorkCoordinator()

    start_calls = 0

    def _record_start() -> None:
        nonlocal start_calls
        start_calls += 1

    monkeypatch.setattr(coordinator, "_start_poll_cycle", _record_start)

    coordinator.set_settings_data(
        {
            "github_polling_enabled": True,
            "github_poll_interval_s": 30,
            "github_poll_startup_delay_s": 1,
        }
    )

    assert start_calls == 0
    assert coordinator._startup_poll_started is False
    assert coordinator._startup_timer.isActive()
    assert coordinator._poll_timer.isActive() is False

    assert _wait_until(lambda: start_calls == 1, timeout_ms=1800)
    assert coordinator._startup_poll_started is True
    assert coordinator._poll_timer.isActive()

    coordinator.set_settings_data({"github_polling_enabled": False})


def test_start_poll_cycle_recovers_after_startup_probe_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _app()
    coordinator = GitHubWorkCoordinator()
    coordinator._settings = {"github_polling_enabled": True}

    eligible_calls = 0

    def _flaky_eligible_env_ids() -> list[str]:
        nonlocal eligible_calls
        eligible_calls += 1
        if eligible_calls == 1:
            raise RuntimeError("startup sequencing not ready")
        return []

    monkeypatch.setattr(
        coordinator,
        "_eligible_poll_environment_ids",
        _flaky_eligible_env_ids,
    )

    coordinator._start_poll_cycle()
    assert eligible_calls == 1
    assert coordinator._poll_cycle_running is False

    coordinator._start_poll_cycle()
    assert eligible_calls == 2
    assert coordinator._poll_cycle_running is False


def test_runtime_toggle_starts_polling_immediately(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _app()
    coordinator = GitHubWorkCoordinator()

    start_calls = 0

    def _record_start() -> None:
        nonlocal start_calls
        start_calls += 1

    monkeypatch.setattr(coordinator, "_start_poll_cycle", _record_start)

    coordinator.set_settings_data(
        {
            "github_polling_enabled": False,
            "github_poll_interval_s": 30,
            "github_poll_startup_delay_s": 30,
        }
    )
    assert start_calls == 0
    assert coordinator._poll_timer.isActive() is False

    coordinator.set_settings_data(
        {
            "github_polling_enabled": True,
            "github_poll_interval_s": 30,
            "github_poll_startup_delay_s": 30,
        }
    )

    assert start_calls == 1
    assert coordinator._startup_poll_started is True
    assert coordinator._startup_timer.isActive() is False
    assert coordinator._poll_timer.isActive()

    coordinator.set_settings_data({"github_polling_enabled": False})


def test_is_polling_effective_ignores_env_checkbox_when_global_enabled() -> None:
    _app()
    coordinator = GitHubWorkCoordinator()
    env_id = "env-1"
    coordinator.set_environments(
        {
            env_id: Environment(
                env_id=env_id,
                name="Env 1",
                workspace_type=WORKSPACE_CLONED,
                workspace_target="Midori-AI-OSS/Agents-Runner",
                github_polling_enabled=False,
            )
        }
    )

    coordinator.set_settings_data(
        {
            "github_polling_enabled": True,
            "github_poll_interval_s": 30,
            "github_poll_startup_delay_s": 0,
        }
    )
    assert coordinator.is_polling_effective_for_env(env_id) is True

    coordinator.set_settings_data({"github_polling_enabled": False})
    assert coordinator.is_polling_effective_for_env(env_id) is False
