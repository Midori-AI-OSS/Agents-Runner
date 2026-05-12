from __future__ import annotations

import runpy
import sys
import types

import pytest


def test_python_dash_m_agents_runner_delegates_to_cli_main(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    fake_cli = types.ModuleType("agents_runner.cli")

    def _fake_main() -> None:
        calls.append("called")

    fake_cli.main = _fake_main

    monkeypatch.setitem(sys.modules, "agents_runner.cli", fake_cli)
    monkeypatch.delitem(sys.modules, "agents_runner.__main__", raising=False)

    runpy.run_module("agents_runner", run_name="__main__", alter_sys=True)

    assert calls == ["called"]
