"""Real-Docker matrix smoke tests for agent and IDE plugin systems.

Phase 1 scope:
- Runtime plugin discovery for agents and IDEs
- Per-agent grouped smoke (agent + interactive)
- Per-IDE smoke with real package preflight install + executable verification
- Case manifest artifact output for downstream review tooling

Deferred work (tracked in manifest `deferred_issues`):
- IDE lifecycle wait-tracking correctness assertions (Phase 2)
- IDE matcher hardening (Phase 2)
- Branch-protection required-check policy wiring outside repo config (Phase 3)
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import tempfile
import threading
import time

from datetime import datetime, timezone
from pathlib import Path
from typing import Final
from typing import TypedDict

import pytest

import agents_runner.docker.agent_worker_setup as agent_worker_setup

from agents_runner.agent_systems import available_agent_system_names
from agents_runner.agent_systems import get_agent_system
from agents_runner.docker.config import DockerRunnerConfig
from agents_runner.docker.process import run_docker
from agents_runner.docker.workers import DockerAgentWorker
from agents_runner.ide_systems import available_ide_system_names
from agents_runner.ide_systems import get_ide_system

TEST_IMAGE: Final[str] = "lunamidori5/pixelarch:emerald"
MANIFEST_PATH: Final[Path] = Path(
    os.environ.get(
        "AGENTS_RUNNER_MATRIX_MANIFEST",
        "/tmp/agents-artifacts/docker-matrix-manifest.json",
    )
)
HELP_REPOS_DIR: Final[str] = "/tmp/agents-runner-help-repos"

AGENT_CASES: Final[tuple[str, ...]] = tuple(available_agent_system_names())
IDE_CASES: Final[tuple[str, ...]] = tuple(available_ide_system_names())


class ModeSummary(TypedDict):
    mode: str
    exit_code: int
    error: str | None
    duration_s: float
    log_lines: int
    state_updates: int


class CaseSummary(TypedDict):
    case_id: str
    category: str
    plugin: str
    status: str
    duration_s: float
    started_at: str
    modes: list[ModeSummary]
    notes: list[str]


class WorkerResult(TypedDict):
    exit_code: int
    error: str | None
    logs: list[str]
    states: list[dict[str, object]]
    duration_s: float


_CASE_REPORTS: list[CaseSummary] = []
_image_ready = False
_DEFERRED_ISSUES: Final[list[dict[str, str]]] = [
    {
        "id": "phase2-ide-lifecycle-wait-tracking",
        "title": "IDE lifecycle attach/wait tracking can report success on missing tracked PID",
        "scope": "Phase 2",
    },
    {
        "id": "phase2-ide-matcher-hardening",
        "title": "IDE wait-process matcher precision/portability hardening (especially Cursor)",
        "scope": "Phase 2",
    },
    {
        "id": "phase3-required-check-policy",
        "title": "Configure repository branch protection to require Docker Matrix workflow check",
        "scope": "Phase 3",
    },
]


def _can_access_docker() -> bool:
    try:
        subprocess.run(
            ["docker", "ps"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5.0,
        )
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _can_access_docker(),
    reason="Docker is not accessible. This matrix requires Docker socket access.",
)


def _cleanup_test_containers() -> None:
    try:
        raw = run_docker(
            [
                "ps",
                "-a",
                "--filter",
                "name=agents-runner-matrix-",
                "--format",
                "{{.ID}}",
            ],
            timeout_s=10.0,
        )
    except Exception:
        return
    container_ids = [line.strip() for line in raw.splitlines() if line.strip()]
    for container_id in container_ids:
        try:
            run_docker(["rm", "-f", container_id], timeout_s=15.0)
        except Exception:
            pass


def _record_case(summary: CaseSummary) -> None:
    _CASE_REPORTS.append(summary)


def _write_manifest() -> None:
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "image": TEST_IMAGE,
        "discovered_plugins": {
            "agents": list(AGENT_CASES),
            "ides": list(IDE_CASES),
        },
        "case_counts": {
            "agent_grouped_cases": len(AGENT_CASES),
            "ide_cases": len(IDE_CASES),
            "top_level_total": len(AGENT_CASES) + len(IDE_CASES),
        },
        "deferred_issues": list(_DEFERRED_ISSUES),
        "cases": sorted(_CASE_REPORTS, key=lambda item: item["case_id"]),
    }
    MANIFEST_PATH.write_text(
        f"{json.dumps(payload, indent=2, sort_keys=True)}\n",
        encoding="utf-8",
    )


def _ensure_test_image() -> None:
    global _image_ready
    if _image_ready:
        return
    try:
        run_docker(["image", "inspect", TEST_IMAGE], timeout_s=20.0)
    except Exception:
        run_docker(["pull", TEST_IMAGE], timeout_s=900.0)
    _image_ready = True


def _safe_package_name(package_name: str) -> str:
    return "".join(
        ch for ch in str(package_name or "").strip() if ch.isalnum() or ch in "-_."
    )


def _run_worker_case(
    *,
    case_token: str,
    launch_mode: str,
    agent_cli: str,
    custom_command_argv: list[str],
    custom_verify_executable: str = "",
    custom_wait_process_pattern: str = "",
    ide_system: str = "",
    ide_preflight_script: str | None = None,
    timeout_s: float = 900.0,
) -> WorkerResult:
    _ensure_test_image()

    with (
        tempfile.TemporaryDirectory(
            prefix=f"agents-runner-matrix-{case_token}-workspace-"
        ) as host_workdir,
        tempfile.TemporaryDirectory(
            prefix=f"agents-runner-matrix-{case_token}-config-"
        ) as host_config_dir,
    ):
        done = threading.Event()
        logs: list[str] = []
        states: list[dict[str, object]] = []
        result: dict[str, object] = {"exit_code": None, "error": None}

        task_id = f"matrix-{case_token}-{int(time.time() * 1000)}"
        container_name = f"agents-runner-matrix-{task_id}"[:63]
        config = DockerRunnerConfig(
            task_id=task_id,
            image=TEST_IMAGE,
            host_workdir=host_workdir,
            host_config_dir=host_config_dir,
            container_workdir="/home/midori-ai/workspace",
            agent_cli=agent_cli,
            launch_mode=launch_mode,
            ide_system=ide_system,
            pull_before_run=False,
            auto_remove=True,
            custom_command_argv=list(custom_command_argv),
            custom_verify_executable=str(custom_verify_executable or ""),
            custom_wait_process_pattern=str(custom_wait_process_pattern or ""),
            ide_preflight_script=ide_preflight_script,
            container_name=container_name,
        )

        def _on_done(code: int, err: str | None, _artifacts: list[str]) -> None:
            result["exit_code"] = int(code)
            result["error"] = None if err is None else str(err)
            done.set()

        worker = DockerAgentWorker(
            config=config,
            prompt="matrix smoke run",
            on_state=lambda state: states.append(
                {str(key): state[key] for key in state.keys()}
            ),
            on_log=lambda line: logs.append(str(line)),
            on_done=_on_done,
        )

        started_s = time.monotonic()
        thread = threading.Thread(target=worker.run, daemon=True)
        thread.start()
        thread.join(timeout=timeout_s)
        if not done.is_set():
            worker.request_kill()
            thread.join(timeout=5.0)
            raise TimeoutError(
                f"worker timed out after {timeout_s:.1f}s "
                f"(case={case_token}, mode={launch_mode})"
            )

        exit_code_raw = result.get("exit_code")
        if not isinstance(exit_code_raw, int):
            raise RuntimeError(f"worker did not report exit code (case={case_token})")

        error_raw = result.get("error")
        error = str(error_raw) if isinstance(error_raw, str) else None
        return {
            "exit_code": exit_code_raw,
            "error": error,
            "logs": list(logs),
            "states": list(states),
            "duration_s": time.monotonic() - started_s,
        }


def _mode_summary(mode: str, result: WorkerResult) -> ModeSummary:
    return {
        "mode": mode,
        "exit_code": int(result["exit_code"]),
        "error": result["error"],
        "duration_s": round(float(result["duration_s"]), 3),
        "log_lines": len(result["logs"]),
        "state_updates": len(result["states"]),
    }


@pytest.fixture(scope="module", autouse=True)
def module_setup_and_manifest() -> object:
    # Speed + determinism for matrix runs: disable bundled system preflight updates.
    with tempfile.TemporaryDirectory(prefix="agents-runner-matrix-preflights-") as tmp:
        preflights_dir = Path(tmp)
        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(agent_worker_setup, "PREFLIGHTS_DIR", preflights_dir)
        _cleanup_test_containers()
        try:
            yield
        finally:
            _cleanup_test_containers()
            monkeypatch.undo()
            _write_manifest()


@pytest.mark.parametrize("agent_name", AGENT_CASES, ids=lambda name: f"agent-{name}")
def test_agent_plugin_grouped_smoke(agent_name: str) -> None:
    plugin = get_agent_system(agent_name)
    case_id = f"agent-grouped-{agent_name}"
    started_at = datetime.now(timezone.utc).isoformat()
    started_s = time.monotonic()
    mode_summaries: list[ModeSummary] = []
    notes = [
        "grouped case executes both agent and interactive smoke paths for one plugin"
    ]
    status = "passed"
    failure_detail = ""

    try:
        verify_cmd = [str(part) for part in plugin.verify_command()]
        assert verify_cmd, f"{agent_name}: empty verify_command()"
        agent_result = _run_worker_case(
            case_token=f"{agent_name}-agent",
            launch_mode="agent",
            agent_cli=agent_name,
            custom_command_argv=verify_cmd,
            custom_verify_executable=str(verify_cmd[0]),
            timeout_s=600.0,
        )
        mode_summaries.append(_mode_summary("agent", agent_result))
        assert int(agent_result["exit_code"]) == 0, (
            f"{agent_name} agent smoke failed: exit={agent_result['exit_code']} "
            f"error={agent_result['error']}"
        )

        interactive_parts = plugin.build_interactive_command_parts(
            cmd_parts=[agent_name, "--help"],
            agent_cli_args=[],
            prompt="",
            is_help_launch=False,
            help_repos_dir=HELP_REPOS_DIR,
        )
        assert interactive_parts, f"{agent_name}: empty interactive command parts"
        interactive_result = _run_worker_case(
            case_token=f"{agent_name}-interactive",
            launch_mode="interactive_agent",
            agent_cli=agent_name,
            custom_command_argv=[str(part) for part in interactive_parts],
            custom_verify_executable=str(interactive_parts[0]),
            timeout_s=600.0,
        )
        mode_summaries.append(_mode_summary("interactive", interactive_result))
        assert int(interactive_result["exit_code"]) == 0, (
            f"{agent_name} interactive smoke failed: "
            f"exit={interactive_result['exit_code']} "
            f"error={interactive_result['error']}"
        )
    except Exception as exc:
        status = "failed"
        failure_detail = str(exc)
        raise
    finally:
        if failure_detail:
            notes.append(f"failure_detail={failure_detail}")
        _record_case(
            {
                "case_id": case_id,
                "category": "agent_grouped",
                "plugin": agent_name,
                "status": status,
                "duration_s": round(time.monotonic() - started_s, 3),
                "started_at": started_at,
                "modes": mode_summaries,
                "notes": notes,
            }
        )


@pytest.mark.parametrize("ide_name", IDE_CASES, ids=lambda name: f"ide-{name}")
def test_ide_plugin_smoke(ide_name: str) -> None:
    plugin = get_ide_system(ide_name)
    case_id = f"ide-smoke-{ide_name}"
    started_at = datetime.now(timezone.utc).isoformat()
    started_s = time.monotonic()
    mode_summaries: list[ModeSummary] = []
    status = "passed"
    failure_detail = ""
    executable = str(getattr(plugin, "executable", "") or "").strip()
    package_name = str(getattr(plugin, "package_name", "") or "").strip()
    notes = ["phase-1 ide smoke installs package in-command and verifies executable"]

    try:
        assert executable, f"{ide_name}: missing executable"
        safe_package = _safe_package_name(package_name)
        assert safe_package, f"{ide_name}: missing install package name"

        executable_quoted = shlex.quote(executable)
        package_quoted = shlex.quote(safe_package)
        verification_cmd = [
            "/bin/bash",
            "-lc",
            "set -euo pipefail; "
            f"yay -Syu --noconfirm --needed {package_quoted}; "
            "yay -Yccc --noconfirm; "
            f"command -v {executable_quoted} >/dev/null; "
            "printf 'ide-preflight-ok\\n' >/dev/null",
        ]
        ide_result = _run_worker_case(
            case_token=f"{ide_name}-smoke",
            launch_mode="ide",
            agent_cli="codex",
            custom_command_argv=verification_cmd,
            custom_verify_executable="/bin/bash",
            custom_wait_process_pattern="",
            ide_system=ide_name,
            ide_preflight_script=None,
            timeout_s=1200.0,
        )
        mode_summaries.append(_mode_summary("ide_preflight_and_verify", ide_result))
        assert int(ide_result["exit_code"]) == 0, (
            f"{ide_name} smoke failed: exit={ide_result['exit_code']} "
            f"error={ide_result['error']}"
        )
    except Exception as exc:
        status = "failed"
        failure_detail = str(exc)
        raise
    finally:
        notes.append("phase2 will add lifecycle wait-tracking assertions")
        if failure_detail:
            notes.append(f"failure_detail={failure_detail}")
        _record_case(
            {
                "case_id": case_id,
                "category": "ide",
                "plugin": ide_name,
                "status": status,
                "duration_s": round(time.monotonic() - started_s, 3),
                "started_at": started_at,
                "modes": mode_summaries,
                "notes": notes,
            }
        )
