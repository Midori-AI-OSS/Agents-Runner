from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from agents_runner.environments import Environment
from agents_runner.environments import WORKSPACE_NONE
from agents_runner.terminal_apps import TerminalOption
from agents_runner.ui.main_window_settings import MainWindowSettingsMixin
from agents_runner.ui.main_window_tasks_interactive import (
    MainWindowTasksInteractiveMixin,
)
import agents_runner.ui.main_window_tasks_interactive as interactive_module


class _FakeSignal:
    def connect(self, *_args, **_kwargs) -> None:
        return


class _FakeThread:
    def __init__(self, _parent=None) -> None:
        self.started = _FakeSignal()
        self.finished = _FakeSignal()

    def start(self) -> None:
        return

    def quit(self) -> None:
        return

    def deleteLater(self) -> None:
        return


class _FakePrepWorker:
    def __init__(self, **_kwargs) -> None:
        self.stage = _FakeSignal()
        self.log = _FakeSignal()
        self.succeeded = _FakeSignal()
        self.failed = _FakeSignal()

    def moveToThread(self, _thread) -> None:
        return

    def run(self) -> None:
        return

    def deleteLater(self) -> None:
        return


class _FakePrepBridge:
    def __init__(self, **_kwargs) -> None:
        return

    def on_stage(self, *_args, **_kwargs) -> None:
        return

    def on_log(self, *_args, **_kwargs) -> None:
        return

    def on_succeeded(self, *_args, **_kwargs) -> None:
        return

    def on_failed(self, *_args, **_kwargs) -> None:
        return

    def deleteLater(self) -> None:
        return


class _FakeMessageBox:
    @staticmethod
    def critical(*_args, **_kwargs) -> None:
        return

    @staticmethod
    def warning(*_args, **_kwargs) -> None:
        return


@dataclass
class _DummyDashboard:
    last_task_id: str | None = None

    def upsert_task(self, task, *, stain=None, spinner_color=None) -> None:
        self.last_task_id = task.task_id


class _DummyNewTask:
    def reset_for_new_run(self) -> None:
        return


class _DummyMainWindow(MainWindowSettingsMixin, MainWindowTasksInteractiveMixin):
    def __init__(self, env: Environment, tmp_path: Path, workdir: Path) -> None:
        self._settings_data = {
            "use": "codex",
            "agent_config_dirs": {
                "codex": str(tmp_path / "codex"),
                "copilot": str(tmp_path / "copilot"),
                "claude": str(tmp_path / "claude"),
                "gemini": str(tmp_path / "gemini"),
            },
            "append_pixelarch_context": False,
            "preflight_enabled": False,
            "preflight_script": "",
        }
        self._environments = {env.env_id: env}
        self._tasks: dict[str, object] = {}
        self._interactive_prep_context: dict[str, object] = {}
        self._interactive_prep_workers: dict[str, object] = {}
        self._interactive_prep_threads: dict[str, object] = {}
        self._interactive_prep_bridges: dict[str, object] = {}
        self._dashboard = _DummyDashboard()
        self._new_task = _DummyNewTask()
        self._state_path = str(tmp_path / "state.toml")
        self._workdir = str(workdir)

    def _active_environment_id(self) -> str:
        return next(iter(self._environments.keys()))

    def _new_task_workspace(self, _env, *, task_id: str) -> tuple[str, bool, str]:
        return self._workdir, True, ""

    def _schedule_save(self) -> None:
        return

    def _maybe_auto_navigate_on_task_start(self, *, interactive: bool) -> None:
        return

    def _on_task_log(self, _task_id: str, _line: str) -> None:
        return


def test_interactive_task_uses_codex_default_and_copilot_override(
    monkeypatch, tmp_path
) -> None:
    workdir = tmp_path / "workspace"
    workdir.mkdir(parents=True, exist_ok=True)

    env = Environment(
        env_id="env-override",
        name="Override",
        workspace_type=WORKSPACE_NONE,
        workspace_target=str(workdir),
        agent_cli_args="--env-flag",
    )
    env.midoriai_template_likelihood = 1.0

    window = _DummyMainWindow(env, tmp_path, workdir)
    monkeypatch.setenv("HOME", str(tmp_path))
    window._settings_data["agent_config_dirs"] = {
        "codex": "~/.codex-default",
        "copilot": "~/.copilot-override",
        "claude": str(tmp_path / "claude"),
        "gemini": str(tmp_path / "gemini"),
    }

    terminal_option = TerminalOption(
        terminal_id="test-terminal",
        label="Test",
        kind="linux-exe",
        exe="/bin/true",
    )

    monkeypatch.setattr(
        interactive_module,
        "detect_terminal_options",
        lambda: [terminal_option],
    )
    monkeypatch.setattr(
        interactive_module.shutil,
        "which",
        lambda name: "/usr/bin/docker" if name == "docker" else None,
    )
    monkeypatch.setattr(interactive_module, "QMessageBox", _FakeMessageBox)
    monkeypatch.setattr(interactive_module, "InteractivePrepWorker", _FakePrepWorker)
    monkeypatch.setattr(interactive_module, "InteractivePrepBridge", _FakePrepBridge)
    monkeypatch.setattr(interactive_module, "QThread", _FakeThread)
    monkeypatch.setattr(interactive_module, "is_gh_available", lambda: False)

    window._start_interactive_task_from_ui(
        prompt="default",
        command="echo default",
        host_codex="",
        env_id=env.env_id,
        terminal_id="test-terminal",
        base_branch="",
        agent_override=None,
        extra_preflight_script="",
    )

    assert len(window._tasks) == 1
    default_task_id = window._dashboard.last_task_id
    assert default_task_id is not None
    default_task = window._tasks[default_task_id]
    assert default_task.agent_cli == "codex"
    assert default_task.host_config_dir == str(tmp_path / ".codex-default")
    assert Path(default_task.host_config_dir).is_absolute()
    assert default_task.agent_instance_id == ""
    assert default_task.agent_cli_args == "--env-flag"
    assert (
        window._interactive_prep_context[default_task_id]["command"]
        == "--sandbox danger-full-access"
    )

    override = {
        "agent_cli": "copilot",
        "agent_id": "copilot-1",
        "cli_flags": "--override-flag",
    }

    window._start_interactive_task_from_ui(
        prompt="hello",
        command="--sandbox danger-full-access",
        host_codex=str(tmp_path / "codex-explicit"),
        env_id=env.env_id,
        terminal_id="test-terminal",
        base_branch="",
        agent_override=override,
        extra_preflight_script="",
    )

    assert len(window._tasks) == 2
    override_task_id = window._dashboard.last_task_id
    assert override_task_id is not None
    assert override_task_id != default_task_id
    override_task = window._tasks[override_task_id]
    assert override_task.agent_cli == "copilot"
    assert override_task.agent_instance_id == "copilot-1"
    assert override_task.host_config_dir == str(tmp_path / ".copilot-override")
    assert Path(override_task.host_config_dir).is_absolute()
    assert override_task.host_config_dir != default_task.host_config_dir
    assert override_task.agent_cli_args == "--override-flag"
    override_command = str(
        window._interactive_prep_context[override_task_id]["command"] or ""
    )
    assert "--add-dir /home/midori-ai/workspace" in override_command
