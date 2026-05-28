from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from agents_runner.agent_configs.model import AgentConfig
from agents_runner.agent_configs.storage import save_agent_config
from agents_runner.environments import Environment
from agents_runner.environments import WORKSPACE_NONE
from agents_runner.environments.model import AgentInstance
from agents_runner.environments.model import AgentSelection
from agents_runner.execution.supervisor import SupervisorConfig
from agents_runner.execution.supervisor import TaskSupervisor
from agents_runner.terminal_apps import TerminalOption
from agents_runner.ui.main_window_environment import MainWindowEnvironmentMixin
from agents_runner.ui.main_window_settings import MainWindowSettingsMixin
from agents_runner.ui.main_window_tasks_agent import MainWindowTasksAgentMixin
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


class _CapturingPrepWorker:
    def __init__(self, **kwargs) -> None:
        self.kwargs = dict(kwargs)
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

    @staticmethod
    def information(*_args, **_kwargs) -> None:
        return


@dataclass
class _DummyDashboard:
    last_task_id: str | None = None

    def upsert_task(self, task, *, stain=None, spinner_color=None) -> None:
        del stain, spinner_color
        self.last_task_id = task.task_id

    def remove_tasks(self, _task_ids) -> None:
        return

    def upsert_past_task(self, *_args, **_kwargs) -> None:
        return


class _DummyNewTask:
    def reset_for_new_run(self) -> None:
        return

    def set_agent_info(self, agent: str, next_agent: str = "") -> None:
        del agent, next_agent
        return


class _DummyMainWindowInteractive(
    MainWindowEnvironmentMixin,
    MainWindowSettingsMixin,
    MainWindowTasksInteractiveMixin,
):
    def __init__(self, env: Environment, tmp_path: Path, workdir: Path) -> None:
        self._settings_data = {
            "use": "codex",
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
        del task_id
        return self._workdir, True, ""

    def _schedule_save(self) -> None:
        return

    def _maybe_auto_navigate_on_task_start(self, *, interactive: bool) -> None:
        del interactive
        return

    def _on_task_log(self, _task_id: str, _line: str) -> None:
        return

    def _refresh_new_task_agent_info(self) -> None:
        return

    def _apply_environment_tints(self) -> None:
        return


class _DummyMainWindowAgent(
    MainWindowEnvironmentMixin,
    MainWindowSettingsMixin,
    MainWindowTasksAgentMixin,
):
    def __init__(self, env: Environment, tmp_path: Path, workdir: Path) -> None:
        self._settings_data = {
            "use": "codex",
            "append_pixelarch_context": False,
            "preflight_enabled": False,
            "preflight_script": "",
        }
        self._environments = {env.env_id: env}
        self._tasks: dict[str, object] = {}
        self._threads: dict[str, object] = {}
        self._bridges: dict[str, object] = {}
        self._run_started_s: dict[str, float] = {}
        self._dashboard_log_refresh_s: dict[str, float] = {}
        self._watch_states: dict[str, object] = {}
        self._dashboard = _DummyDashboard()
        self._new_task = _DummyNewTask()
        self._state_path = str(tmp_path / "state.toml")
        self._workdir = str(workdir)

    def _active_environment_id(self) -> str:
        return next(iter(self._environments.keys()))

    def _new_task_workspace(self, _env, *, task_id: str) -> tuple[str, bool, str]:
        del task_id
        return self._workdir, True, ""

    def _schedule_save(self) -> None:
        return

    def _maybe_auto_navigate_on_task_start(self, *, interactive: bool) -> None:
        del interactive
        return

    def _on_task_log(self, _task_id: str, _line: str) -> None:
        return

    def _refresh_new_task_agent_info(self) -> None:
        return

    def _can_start_new_agent_for_env(self, _env_id: str | None) -> bool:
        return False


def test_selected_environment_agent_cli_flags_reach_interactive_launch(
    monkeypatch, tmp_path
) -> None:
    workdir = tmp_path / "workspace"
    workdir.mkdir(parents=True, exist_ok=True)

    save_agent_config(
        str(tmp_path / "state.toml"),
        AgentConfig(
            config_id="opencode-plan",
            agent_cli="opencode",
            config_dir="",
            cli_flags="--agent plan",
        ),
    )
    save_agent_config(
        str(tmp_path / "state.toml"),
        AgentConfig(
            config_id="codex-default",
            agent_cli="codex",
            config_dir="",
            cli_flags="",
        ),
    )

    env = Environment(
        env_id="env-opencode",
        name="OpenCode",
        workspace_type=WORKSPACE_NONE,
        workspace_target=str(workdir),
    )
    env.agent_selection = AgentSelection(
        agents=[
            AgentInstance(
                agent_id="opencode-plan",
                config_id="opencode-plan",
            ),
            AgentInstance(
                agent_id="codex-default",
                config_id="codex-default",
            ),
        ],
        selection_mode="pinned",
        pinned_agent_id="opencode-plan",
        agent_fallbacks={},
    )

    window = _DummyMainWindowInteractive(env, tmp_path, workdir)
    monkeypatch.setenv("HOME", str(tmp_path))

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
    monkeypatch.setattr(
        interactive_module, "InteractivePrepWorker", _CapturingPrepWorker
    )
    monkeypatch.setattr(interactive_module, "InteractivePrepBridge", _FakePrepBridge)
    monkeypatch.setattr(interactive_module, "QThread", _FakeThread)
    monkeypatch.setattr(interactive_module, "is_gh_available", lambda: False)

    window._start_interactive_task_from_ui(
        prompt="hello",
        command="opencode",
        host_config_dir="",
        env_id=env.env_id,
        terminal_id="test-terminal",
        base_branch="",
        agent_override=None,
        extra_preflight_script="",
    )

    task_id = window._dashboard.last_task_id
    assert task_id is not None
    task = window._tasks[task_id]
    assert task.agent_cli == "opencode"
    assert task.agent_instance_id == "opencode-plan"
    assert task.agent_cli_args == "--agent plan"

    worker = window._interactive_prep_workers[task_id]
    assert worker.kwargs.get("agent_cli") == "opencode"
    assert worker.kwargs.get("agent_cli_args") == ["--agent", "plan"]


def test_selected_environment_agent_cli_flags_reach_run_agent_launch(
    monkeypatch, tmp_path
) -> None:
    workdir = tmp_path / "workspace"
    workdir.mkdir(parents=True, exist_ok=True)

    save_agent_config(
        str(tmp_path / "state.toml"),
        AgentConfig(
            config_id="opencode-plan",
            agent_cli="opencode",
            config_dir="",
            cli_flags="--agent plan",
        ),
    )

    env = Environment(
        env_id="env-opencode",
        name="OpenCode",
        workspace_type=WORKSPACE_NONE,
        workspace_target=str(workdir),
    )
    env.agent_selection = AgentSelection(
        agents=[
            AgentInstance(
                agent_id="opencode-plan",
                config_id="opencode-plan",
            )
        ],
        selection_mode="pinned",
        pinned_agent_id="opencode-plan",
        agent_fallbacks={},
    )

    window = _DummyMainWindowAgent(env, tmp_path, workdir)
    monkeypatch.setattr(
        "agents_runner.ui.main_window_tasks_agent.shutil.which",
        lambda name: "/usr/bin/docker" if name == "docker" else None,
    )
    monkeypatch.setattr(
        "agents_runner.ui.main_window_tasks_agent.QMessageBox",
        _FakeMessageBox,
    )
    monkeypatch.setenv("HOME", str(tmp_path))

    task_id = window._start_task_from_ui(
        prompt="hello",
        host_config_dir="",
        env_id=env.env_id,
        base_branch="",
        pr_context=None,
        agent_override=None,
    )
    assert task_id is not None
    task = window._tasks[task_id]
    assert task.agent_cli == "opencode"
    assert task.agent_instance_id == "opencode-plan"
    selection = getattr(task, "_agent_selection", None)
    assert selection is not None
    assert selection.agents[0].config_id == "opencode-plan"

    config = getattr(task, "_runner_config", None)
    assert config is not None
    supervisor = TaskSupervisor(
        config=config,
        prompt="hello",
        agent_selection=selection,
        supervisor_config=SupervisorConfig(
            max_retries_per_agent=0,
            enable_fallback=True,
        ),
        on_state=lambda _state: None,
        on_log=lambda _line: None,
        on_retry=lambda _attempt, _agent, _delay: None,
        on_agent_switch=lambda _from_agent, _to_agent: None,
        on_done=None,
        watch_states={},
        agent_configs={
            "opencode-plan": AgentConfig(
                config_id="opencode-plan",
                agent_cli="opencode",
                config_dir="",
                cli_flags="--agent plan",
            )
        },
    )

    agent_config = supervisor._build_agent_config(selection.agents[0])
    assert agent_config.agent_cli_args == ["--agent", "plan"]
