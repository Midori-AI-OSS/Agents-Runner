"""
Integration smoke test for supervisor.

Tests basic supervisor functionality without Docker.
"""

import time
from agents_runner.execution.supervisor import (
    ErrorType,
    SupervisorConfig,
    TaskSupervisor,
    calculate_backoff,
    classify_error,
)
from agents_runner.docker.config import DockerRunnerConfig
from agents_runner.environments.model import AgentInstance, AgentSelection


def test_agent_chain_building():
    """Test agent chain building from agent_selection."""
    # Create test configuration
    config = DockerRunnerConfig(
        task_id="test-001",
        image="test-image",
        host_codex_dir="/tmp/codex",
        host_workdir="/tmp/workspace",
        agent_cli="codex",
    )

    # Create agent selection with fallback chain
    agents = [
        AgentInstance(agent_id="primary", agent_cli="codex"),
        AgentInstance(agent_id="secondary", agent_cli="claude"),
        AgentInstance(agent_id="tertiary", agent_cli="copilot"),
    ]
    agent_selection = AgentSelection(
        agents=agents,
        selection_mode="fallback",
        agent_fallbacks={
            "primary": "secondary",
            "secondary": "tertiary",
        },
    )

    # Create supervisor
    supervisor = TaskSupervisor(
        config=config,
        prompt="Test prompt",
        agent_selection=agent_selection,
        supervisor_config=SupervisorConfig(),
        on_state=lambda s: None,
        on_log=lambda l: None,
        on_retry=lambda r, a, d: None,
        on_agent_switch=lambda f, t: None,
    )

    # Initialize agent chain
    supervisor._initialize_agent_chain()

    # Verify chain
    assert len(supervisor._agent_chain) == 3
    assert supervisor._agent_chain[0].agent_cli == "codex"
    assert supervisor._agent_chain[1].agent_cli == "claude"
    assert supervisor._agent_chain[2].agent_cli == "copilot"
    print("✓ Agent chain building works correctly")


def test_agent_chain_circular_detection():
    """Test circular fallback detection."""
    config = DockerRunnerConfig(
        task_id="test-002",
        image="test-image",
        host_codex_dir="/tmp/codex",
        host_workdir="/tmp/workspace",
        agent_cli="codex",
    )

    # Create circular fallback
    agents = [
        AgentInstance(agent_id="a", agent_cli="codex"),
        AgentInstance(agent_id="b", agent_cli="claude"),
    ]
    agent_selection = AgentSelection(
        agents=agents,
        agent_fallbacks={
            "a": "b",
            "b": "a",  # Circular!
        },
    )

    supervisor = TaskSupervisor(
        config=config,
        prompt="Test prompt",
        agent_selection=agent_selection,
        supervisor_config=SupervisorConfig(),
        on_state=lambda s: None,
        on_log=lambda l: None,
        on_retry=lambda r, a, d: None,
        on_agent_switch=lambda f, t: None,
    )

    supervisor._initialize_agent_chain()

    # Should stop at circular reference
    assert len(supervisor._agent_chain) == 2
    assert supervisor._agent_chain[0].agent_id == "a"
    assert supervisor._agent_chain[1].agent_id == "b"
    print("✓ Circular fallback detection works correctly")


def test_agent_chain_default():
    """Test default agent when no selection."""
    config = DockerRunnerConfig(
        task_id="test-003",
        image="test-image",
        host_codex_dir="/tmp/codex",
        host_workdir="/tmp/workspace",
        agent_cli="codex",
    )

    supervisor = TaskSupervisor(
        config=config,
        prompt="Test prompt",
        agent_selection=None,  # No selection
        supervisor_config=SupervisorConfig(),
        on_state=lambda s: None,
        on_log=lambda l: None,
        on_retry=lambda r, a, d: None,
        on_agent_switch=lambda f, t: None,
    )

    supervisor._initialize_agent_chain()

    # Should use default from config
    assert len(supervisor._agent_chain) == 1
    assert supervisor._agent_chain[0].agent_cli == "codex"
    assert supervisor._agent_chain[0].agent_id == "default"
    print("✓ Default agent selection works correctly")


def test_config_building():
    """Test agent-specific config building."""
    config = DockerRunnerConfig(
        task_id="test-004",
        image="test-image",
        host_codex_dir="/tmp/codex",
        host_workdir="/tmp/workspace",
        agent_cli="codex",
        agent_cli_args=["--verbose"],
        env_vars={"TEST": "value"},
    )

    agent = AgentInstance(
        agent_id="custom",
        agent_cli="claude",
        config_dir="/tmp/claude-config",
        cli_flags="--debug --fast",
    )

    supervisor = TaskSupervisor(
        config=config,
        prompt="Test prompt",
        agent_selection=None,
        supervisor_config=SupervisorConfig(),
        on_state=lambda s: None,
        on_log=lambda l: None,
        on_retry=lambda r, a, d: None,
        on_agent_switch=lambda f, t: None,
    )

    agent_config = supervisor._build_agent_config(agent)

    # Verify overrides
    assert agent_config.agent_cli == "claude"
    assert agent_config.host_codex_dir == "/tmp/claude-config"
    assert agent_config.agent_cli_args == ["--debug", "--fast"]

    # Verify inherited
    assert agent_config.task_id == "test-004"
    assert agent_config.image == "test-image"
    assert agent_config.host_workdir == "/tmp/workspace"
    assert agent_config.env_vars == {"TEST": "value"}

    print("✓ Agent config building works correctly")


def test_properties():
    """Test supervisor properties."""
    config = DockerRunnerConfig(
        task_id="test-005",
        image="test-image",
        host_codex_dir="/tmp/codex",
        host_workdir="/tmp/workspace",
        agent_cli="codex",
    )

    supervisor = TaskSupervisor(
        config=config,
        prompt="Test prompt",
        agent_selection=None,
        supervisor_config=SupervisorConfig(),
        on_state=lambda s: None,
        on_log=lambda l: None,
        on_retry=lambda r, a, d: None,
        on_agent_switch=lambda f, t: None,
    )

    # Properties should return None when no worker
    assert supervisor.container_id is None
    assert supervisor.gh_repo_root is None
    assert supervisor.gh_base_branch is None
    assert supervisor.gh_branch is None

    print("✓ Supervisor properties work correctly")


if __name__ == "__main__":
    print("Running supervisor integration smoke tests...\n")

    test_agent_chain_building()
    test_agent_chain_circular_detection()
    test_agent_chain_default()
    test_config_building()
    test_properties()

    print("\n✓ All integration smoke tests passed!")
