"""Tests for planner module."""

from pathlib import Path

import pytest

from agents_runner.agent_systems.registry import discover_plugins
from agents_runner.planner.models import EnvironmentSpec, RunRequest
from agents_runner.planner.planner import (
    INTERACTIVE_PREFIX,
    plan_run,
)


@pytest.fixture(scope="module", autouse=True)
def setup_plugins() -> None:
    """Discover and register plugins before running tests."""
    discover_plugins()


def test_plan_run_basic() -> None:
    """Test basic run planning with minimal configuration."""
    env = EnvironmentSpec(
        env_id="test-env",
        image="python:3.13",
    )
    request = RunRequest(
        system_name="codex",
        prompt="Test prompt",
        environment=env,
        host_workdir=Path("/tmp/workspace"),
        host_config_dir=Path("/tmp/config"),
    )

    plan = plan_run(request)

    # Verify basic structure
    assert plan.interactive is False
    assert plan.docker.image == "python:3.13"
    assert plan.prompt_text == "Test prompt"
    assert len(plan.exec_spec.argv) > 0
    assert plan.exec_spec.tty is False
    assert plan.exec_spec.stdin is False


def test_plan_run_interactive() -> None:
    """Test interactive run planning includes guardrail prefix."""
    env = EnvironmentSpec(
        env_id="test-env",
        image="python:3.13",
    )
    request = RunRequest(
        interactive=True,
        system_name="codex",
        prompt="Interactive test",
        environment=env,
        host_workdir=Path("/tmp/workspace"),
        host_config_dir=Path("/tmp/config"),
    )

    plan = plan_run(request)

    # Verify interactive settings
    assert plan.interactive is True
    assert plan.prompt_text.startswith(INTERACTIVE_PREFIX)
    assert "Interactive test" in plan.prompt_text
    assert plan.exec_spec.tty is True
    assert plan.exec_spec.stdin is True


def test_plan_run_with_env_vars() -> None:
    """Test environment variables are propagated to docker spec."""
    env = EnvironmentSpec(
        env_id="test-env",
        image="python:3.13",
        env_vars={"FOO": "bar", "BAZ": "qux"},
    )
    request = RunRequest(
        system_name="codex",
        prompt="Test",
        environment=env,
        host_workdir=Path("/tmp/workspace"),
        host_config_dir=Path("/tmp/config"),
    )

    plan = plan_run(request)

    assert "FOO" in plan.docker.env
    assert plan.docker.env["FOO"] == "bar"
    assert "BAZ" in plan.docker.env
    assert plan.docker.env["BAZ"] == "qux"


def test_plan_run_with_extra_mounts() -> None:
    """Test extra mounts are parsed and added to docker spec."""
    env = EnvironmentSpec(
        env_id="test-env",
        image="python:3.13",
        extra_mounts=[
            "/host/path1:/container/path1:ro",
            "/host/path2:/container/path2",
            "/host/path3:/container/path3:rw",
        ],
    )
    request = RunRequest(
        system_name="codex",
        prompt="Test",
        environment=env,
        host_workdir=Path("/tmp/workspace"),
        host_config_dir=Path("/tmp/config"),
    )

    plan = plan_run(request)

    # Should have workspace mount + config mount + plugin mounts + 3 extra mounts
    assert len(plan.docker.mounts) >= 6

    # Find the extra mounts (look for the specific paths we added)
    mount_paths = [(str(m.src), str(m.dst), m.mode) for m in plan.docker.mounts]

    assert ("/host/path1", "/container/path1", "ro") in mount_paths
    assert ("/host/path2", "/container/path2", "rw") in mount_paths
    assert ("/host/path3", "/container/path3", "rw") in mount_paths


def test_plan_run_with_extra_cli_args() -> None:
    """Test extra CLI arguments are included in exec spec."""
    env = EnvironmentSpec(
        env_id="test-env",
        image="python:3.13",
    )
    request = RunRequest(
        system_name="codex",
        prompt="Test",
        environment=env,
        host_workdir=Path("/tmp/workspace"),
        host_config_dir=Path("/tmp/config"),
        extra_cli_args=["--verbose", "--debug"],
    )

    plan = plan_run(request)

    # Extra args should be in the command argv
    argv_str = " ".join(plan.exec_spec.argv)
    assert "--verbose" in argv_str
    assert "--debug" in argv_str


def test_plan_run_mounts_include_workspace_and_config() -> None:
    """Test that plan includes workspace and config mounts."""
    env = EnvironmentSpec(
        env_id="test-env",
        image="python:3.13",
    )
    request = RunRequest(
        system_name="codex",
        prompt="Test",
        environment=env,
        host_workdir=Path("/tmp/workspace"),
        host_config_dir=Path("/tmp/config"),
    )

    plan = plan_run(request)

    # Should have workspace, config, and plugin-specific mounts
    assert len(plan.docker.mounts) >= 2

    # Check workspace mount exists
    workspace_mounts = [
        m for m in plan.docker.mounts if m.src == Path("/tmp/workspace")
    ]
    assert len(workspace_mounts) == 1
    assert workspace_mounts[0].mode == "rw"

    # Check config mount exists
    config_mounts = [m for m in plan.docker.mounts if m.src == Path("/tmp/config")]
    assert len(config_mounts) == 1
    assert config_mounts[0].mode == "rw"


def test_plan_run_artifacts_are_set() -> None:
    """Test that artifact collection paths are configured."""
    env = EnvironmentSpec(
        env_id="test-env",
        image="python:3.13",
    )
    request = RunRequest(
        system_name="codex",
        prompt="Test",
        environment=env,
        host_workdir=Path("/tmp/workspace"),
        host_config_dir=Path("/tmp/config"),
    )

    plan = plan_run(request)

    # Verify artifact paths are set
    assert plan.artifacts.finish_file is not None
    assert plan.artifacts.output_file is not None
    assert plan.artifacts.finish_file.is_absolute()
    assert plan.artifacts.output_file.is_absolute()


def test_plan_run_invalid_mount_format_ignored() -> None:
    """Test that invalid mount formats are silently ignored."""
    env = EnvironmentSpec(
        env_id="test-env",
        image="python:3.13",
        extra_mounts=[
            "invalid_mount_no_colon",
            "only_one_part:",
            ":missing_src",
        ],
    )
    request = RunRequest(
        system_name="codex",
        prompt="Test",
        environment=env,
        host_workdir=Path("/tmp/workspace"),
        host_config_dir=Path("/tmp/config"),
    )

    plan = plan_run(request)

    # Should have workspace + config + plugin mounts (invalid ones ignored)
    # We just verify the invalid ones are not present
    mount_paths = [str(m.src) for m in plan.docker.mounts]
    assert "invalid_mount_no_colon" not in mount_paths
    assert "only_one_part:" not in mount_paths
    assert "" not in mount_paths


def test_plan_run_relative_mount_paths_ignored() -> None:
    """Test that relative mount paths are ignored."""
    env = EnvironmentSpec(
        env_id="test-env",
        image="python:3.13",
        extra_mounts=[
            "relative/src:/absolute/dst",
            "/absolute/src:relative/dst",
        ],
    )
    request = RunRequest(
        system_name="codex",
        prompt="Test",
        environment=env,
        host_workdir=Path("/tmp/workspace"),
        host_config_dir=Path("/tmp/config"),
    )

    plan = plan_run(request)

    # Should have workspace + config + plugin mounts (relative paths ignored)
    # Verify the relative paths are not present
    mount_paths = [(str(m.src), str(m.dst)) for m in plan.docker.mounts]
    # These should not be in the mounts because they have relative paths
    assert ("relative/src", "/absolute/dst") not in mount_paths
    assert ("/absolute/src", "relative/dst") not in mount_paths


def test_plan_run_invalid_mount_mode_defaults_to_rw() -> None:
    """Test that invalid mount modes default to read-write."""
    env = EnvironmentSpec(
        env_id="test-env",
        image="python:3.13",
        extra_mounts=[
            "/host/path:/container/path:invalid_mode",
        ],
    )
    request = RunRequest(
        system_name="codex",
        prompt="Test",
        environment=env,
        host_workdir=Path("/tmp/workspace"),
        host_config_dir=Path("/tmp/config"),
    )

    plan = plan_run(request)

    # Find the extra mount
    extra_mounts = [m for m in plan.docker.mounts if str(m.src) == "/host/path"]
    assert len(extra_mounts) == 1
    assert extra_mounts[0].mode == "rw"


def test_plan_run_workdir_is_set() -> None:
    """Test that container workdir is properly configured."""
    env = EnvironmentSpec(
        env_id="test-env",
        image="python:3.13",
    )
    request = RunRequest(
        system_name="codex",
        prompt="Test",
        environment=env,
        host_workdir=Path("/tmp/workspace"),
        host_config_dir=Path("/tmp/config"),
    )

    plan = plan_run(request)

    # Verify workdir is set and absolute
    assert plan.docker.workdir.is_absolute()
    assert plan.exec_spec.cwd is not None
    assert plan.exec_spec.cwd.is_absolute()
