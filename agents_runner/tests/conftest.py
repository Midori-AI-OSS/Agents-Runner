"""Shared test fixtures and utilities."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def temp_artifacts_dir(tmp_path: Path) -> Path:
    """Create temporary artifacts directory for tests."""
    artifacts_dir = tmp_path / "agents-artifacts"
    artifacts_dir.mkdir(parents=True)
    return artifacts_dir


@pytest.fixture
def temp_workdir(tmp_path: Path) -> Path:
    """Create temporary workspace directory for tests."""
    workdir = tmp_path / "workspace"
    workdir.mkdir(parents=True)
    return workdir


@pytest.fixture
def temp_codex_dir(tmp_path: Path) -> Path:
    """Create temporary codex config directory for tests."""
    codex_dir = tmp_path / "codex"
    codex_dir.mkdir(parents=True)
    return codex_dir


@pytest.fixture
def mock_docker_config(
    temp_workdir: Path,
    temp_codex_dir: Path,
    temp_artifacts_dir: Path,
) -> Any:
    """Create a mock DockerRunnerConfig for testing."""
    # Import here to avoid circular import during module load
    from agents_runner.docker.config import DockerRunnerConfig
    
    return DockerRunnerConfig(
        image="test-agent-runner:latest",
        agent_cli="codex",
        agent_cli_args=[],
        host_workdir=str(temp_workdir),
        container_workdir="/workspace",
        host_codex_dir=str(temp_codex_dir),
        artifacts_out_dir=str(temp_artifacts_dir),
        env_vars={},
        extra_mounts=[],
        environment_id=None,
        headless_desktop_enabled=False,
        gh_context_enabled=False,
        gh_context_file_path=None,
        gh_context_repo_url=None,
        gh_context_base_branch=None,
        gh_context_branch=None,
    )


@pytest.fixture
def mock_callbacks() -> dict[str, MagicMock]:
    """Create mock callback functions for testing."""
    return {
        "on_state": MagicMock(),
        "on_log": MagicMock(),
        "on_retry": MagicMock(),
        "on_agent_switch": MagicMock(),
        "on_done": MagicMock(),
    }


def create_mock_docker_inspect_response(
    exit_code: int = 0,
    oom_killed: bool = False,
) -> dict[str, Any]:
    """Create a mock docker inspect response."""
    return {
        "State": {
            "ExitCode": exit_code,
            "OOMKilled": oom_killed,
            "Running": False,
            "Paused": False,
            "Restarting": False,
            "Dead": False,
        }
    }


def create_success_log_lines() -> list[str]:
    """Create mock log lines for a successful agent execution."""
    return [
        "[agent] starting task execution",
        "[agent] analyzing prompt",
        "[agent] task completed successfully",
        "[agent] artifacts written to /tmp/agents-artifacts",
    ]


def create_rate_limit_log_lines() -> list[str]:
    """Create mock log lines for a rate limit error."""
    return [
        "[agent] starting task execution",
        "[agent] making API request",
        "[error] rate limit exceeded",
        "[error] HTTP 429: too many requests",
        "[error] retry after 60 seconds",
    ]


def create_fatal_error_log_lines() -> list[str]:
    """Create mock log lines for a fatal authentication error."""
    return [
        "[agent] starting task execution",
        "[agent] initializing API client",
        "[error] authentication failed",
        "[error] invalid API key",
        "[error] please check your credentials",
    ]
