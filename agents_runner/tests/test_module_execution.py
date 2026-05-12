from __future__ import annotations

import runpy
import sys
import types

import pytest


def test_python_dash_m_agents_runner_delegates_to_cli_main(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    mock_cli_module = types.ModuleType("agents_runner.cli")

    def _record_call() -> None:
        calls.append("called")

    mock_cli_module.main = _record_call

    monkeypatch.setitem(sys.modules, "agents_runner.cli", mock_cli_module)
    monkeypatch.delitem(sys.modules, "agents_runner.__main__", raising=False)

    runpy.run_module("agents_runner", run_name="__main__", alter_sys=True)

    assert calls == ["called"]
