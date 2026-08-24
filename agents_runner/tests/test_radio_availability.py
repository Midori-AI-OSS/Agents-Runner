# pyright: reportPrivateUsage=false
from __future__ import annotations

import os
from types import SimpleNamespace
from typing import Any

import pytest
from PySide6.QtCore import QTimer
from PySide6.QtNetwork import QNetworkReply
from PySide6.QtWidgets import QApplication

from agents_runner.ui.main_window_environment import MainWindowEnvironmentMixin
from agents_runner.ui.graphics import theme_name_for_agent
from agents_runner.ui.pages.settings import SettingsPage
from agents_runner.ui.radio.controller import RadioController

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        return QApplication([])
    if not isinstance(app, QApplication):
        pytest.skip("QApplication is required for radio availability tests.")
    return app


def _controller_with_fake_probe(monkeypatch: pytest.MonkeyPatch) -> RadioController:
    _app()
    monkeypatch.setattr(
        RadioController,
        "probe_qt_multimedia_available",
        classmethod(lambda _cls: True),
    )
    controller = RadioController()
    monkeypatch.setattr(controller, "_initialize_runtime", lambda: None)
    return controller


def test_startup_readiness_requires_both_valid_responses(monkeypatch: pytest.MonkeyPatch) -> None:
    controller = _controller_with_fake_probe(monkeypatch)
    assert controller.radio_available is False
    assert controller._health_timer is None
    assert controller._current_timer is None
    requested: list[str] = []

    def _request(endpoint: str, callback: Any, **_kwargs: Any) -> None:
        requested.append(endpoint)
        if endpoint == controller.HEALTH_ENDPOINT:
            callback({"ok": True}, "")
            return
        callback({"ok": True, "data": {"track_id": "track-1", "title": "Track"}}, "")

    monkeypatch.setattr(controller, "_request_json", _request)

    assert controller.await_startup_readiness() is True
    assert requested[:2] == [controller.HEALTH_ENDPOINT, controller.CURRENT_ENDPOINT]
    assert controller.radio_available is True
    assert controller.state_snapshot()["startup_readiness_complete"] is True


def test_startup_failure_latches_without_blocking_other_state(monkeypatch: pytest.MonkeyPatch) -> None:
    controller = _controller_with_fake_probe(monkeypatch)

    def _request(_endpoint: str, callback: Any, **_kwargs: Any) -> None:
        callback(None, "service offline")

    monkeypatch.setattr(controller, "_request_json", _request)

    assert controller.await_startup_readiness() is False
    assert controller.radio_available is False
    assert controller.state_snapshot()["radio_latched_off"] is True
    assert controller.start_playback() is False


def test_startup_timeout_is_bounded_and_latched(monkeypatch: pytest.MonkeyPatch) -> None:
    controller = _controller_with_fake_probe(monkeypatch)
    controller.STARTUP_READINESS_TIMEOUT_MS = 1
    monkeypatch.setattr(controller, "_request_json", lambda *_args, **_kwargs: None)

    assert controller.await_startup_readiness() is False
    assert controller.radio_available is False
    assert controller.state_snapshot()["radio_latched_off"] is True


def test_runtime_media_failure_is_permanent_and_stops_timers(monkeypatch: pytest.MonkeyPatch) -> None:
    controller = _controller_with_fake_probe(monkeypatch)
    monkeypatch.setattr(
        controller,
        "_request_json",
        lambda endpoint, callback, **_kwargs: callback(
            {"ok": True} if endpoint == controller.HEALTH_ENDPOINT else {"ok": True, "data": {}},
            "",
        ),
    )
    assert controller.await_startup_readiness() is True

    health_timer = QTimer(controller)
    current_timer = QTimer(controller)
    watchdog_timer = QTimer(controller)
    health_timer.start(60_000)
    current_timer.start(60_000)
    watchdog_timer.start(60_000)
    controller._health_timer = health_timer
    controller._current_timer = current_timer
    controller._watchdog_timer = watchdog_timer
    controller._runtime_timers_active = True
    controller._enabled = True
    controller._desired_playing = True

    controller._on_media_error(None, "stream failed")

    assert controller.radio_available is False
    assert controller.state_snapshot()["radio_latched_off"] is True
    assert health_timer.isActive() is False
    assert current_timer.isActive() is False
    assert watchdog_timer.isActive() is False
    assert controller.start_playback() is False


def test_latch_aborts_pending_reply_and_ignores_late_callback(monkeypatch: pytest.MonkeyPatch) -> None:
    controller = _controller_with_fake_probe(monkeypatch)
    monkeypatch.setattr(
        controller,
        "_request_json",
        lambda endpoint, callback, **_kwargs: callback(
            {"ok": True} if endpoint == controller.HEALTH_ENDPOINT else {"ok": True, "data": {}},
            "",
        ),
    )
    assert controller.await_startup_readiness() is True

    class _Reply:
        def __init__(self) -> None:
            self.aborted = False
            self.deleted = False

        def abort(self) -> None:
            self.aborted = True

        def deleteLater(self) -> None:
            self.deleted = True

        def error(self) -> QNetworkReply.NetworkError:
            return QNetworkReply.NetworkError.NoError

        def errorString(self) -> str:
            return ""

        def readAll(self) -> bytes:
            return b'{"ok": true}'

    reply = _Reply()
    controller._pending_replies.add(reply)  # pyright: ignore[reportArgumentType]
    old_generation = controller._request_generation
    callback_called = False

    def _late_callback(_payload: Any, _error_text: str) -> None:
        nonlocal callback_called
        callback_called = True

    controller._latch_unavailable("service went offline")
    controller._on_json_reply(reply, controller.HEALTH_ENDPOINT, _late_callback, old_generation)  # pyright: ignore[reportArgumentType]

    assert reply.aborted is True
    assert reply.deleted is True
    assert controller._request_generation == old_generation + 1
    assert callback_called is False
    assert controller.radio_available is False


def test_optional_art_and_channel_failures_do_not_latch(monkeypatch: pytest.MonkeyPatch) -> None:
    controller = _controller_with_fake_probe(monkeypatch)
    monkeypatch.setattr(
        controller,
        "_request_json",
        lambda endpoint, callback, **_kwargs: callback(
            {"ok": True} if endpoint == controller.HEALTH_ENDPOINT else {"ok": True, "data": {}},
            "",
        ),
    )
    assert controller.await_startup_readiness() is True

    channel_result: list[tuple[Any, str]] = []

    def _optional_failure(_endpoint: str, callback: Any, **_kwargs: Any) -> None:
        callback(None, "optional endpoint unavailable")

    monkeypatch.setattr(controller, "_request_json", _optional_failure)
    controller._fetch_art("ambient")
    controller.fetch_channels(lambda channels, error: channel_result.append((channels, error)))

    assert controller.radio_available is True
    assert channel_result == [(None, "optional endpoint unavailable")]


def test_settings_remove_radio_and_preserve_dynamic_theme_preference(tmp_path: Any) -> None:
    _app()
    page = SettingsPage(radio_supported=True)
    page._state_path = str(tmp_path / "state.json")
    page.set_settings({"ui_theme": "dynamic", "use": "codex"})
    page.navigate_to_pane("radio")

    page.set_radio_supported(False, preserve_dynamic_theme=True)

    assert page.active_pane_key() == "general_preferences"
    assert page._nav_buttons["radio"].isVisible() is False
    assert page._compact_nav.findData("radio") == -1
    assert page.get_settings()["ui_theme"] == "dynamic"
    assert page._ui_theme.findData("dynamic") == -1

    page.deleteLater()


def test_settings_offline_dynamic_theme_uses_static_agent_fallback(tmp_path: Any) -> None:
    _app()
    page = SettingsPage(radio_supported=False)
    page._state_path = str(tmp_path / "state.json")
    page.set_settings({"ui_theme": "dynamic", "use": "codex"})

    assert page.get_settings()["ui_theme"] == "dynamic"
    assert page._ui_theme.currentData() == theme_name_for_agent("codex")
    assert page._ui_theme.findData("dynamic") == -1

    page.deleteLater()


def test_dynamic_theme_falls_back_to_agent_theme_when_radio_is_offline() -> None:
    class _Root:
        def __init__(self) -> None:
            self.agent_theme_calls: list[str] = []
            self.named_theme_calls: list[str] = []

        def set_agent_theme(self, agent_cli: str) -> None:
            self.agent_theme_calls.append(agent_cli)

        def set_theme_name(self, theme_name: str) -> None:
            self.named_theme_calls.append(theme_name)

    class _NewTask:
        def set_environment_agents(self, _agents: Any) -> None:
            pass

        def set_workspace_status(self, *, path: str, ready: bool, message: str) -> None:
            pass

        def set_agent_info(self, *, agent: str, next_agent: str) -> None:
            pass

        def set_interactive_defaults(self, *, terminal_id: str, command: str) -> None:
            pass

    root = _Root()
    harness = object.__new__(MainWindowEnvironmentMixin)
    harness._settings_data = {"ui_theme": "dynamic", "active_environment_id": "default"}
    harness._environments = {}
    harness._root = root
    harness._new_task = _NewTask()
    harness._radio_controller = SimpleNamespace(
        radio_available=False,
        state_snapshot=lambda: {"radio_available": False},
    )
    harness._active_environment_id = lambda: "default"
    harness._effective_agent_and_config = lambda **_kwargs: ("codex", "", "")
    harness._get_next_agent_info = lambda **_kwargs: ("codex", "codex")
    harness._new_task_workspace = lambda _env: ("", False, "not ready")
    harness._sync_new_task_repo_controls = lambda *_args, **_kwargs: None
    harness._default_interactive_command = lambda _agent_cli: ""
    harness._populate_environment_pickers = lambda: None
    harness._update_window_title_from_radio_state = lambda _state: None

    harness._apply_active_environment_to_new_task()

    assert root.agent_theme_calls == ["codex"]
    assert root.named_theme_calls == []
