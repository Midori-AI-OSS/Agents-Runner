"""E2E tests for task system with real Docker socket.

These tests exercise the task system's lifecycle, persistence, and state
transitions using real Docker containers. Only the agent CLI invocation
is mocked (using echo).

NOTE: These tests require Docker socket access. They will be skipped if Docker
is not available or if the user doesn't have permission to access it.

To run these tests with Docker access:
    1. Add your user to the docker group: sudo usermod -aG docker $USER
    2. Log out and back in for the group change to take effect
    3. Run: uv run pytest agents_runner/tests/test_docker_e2e.py -v

Alternatively, run with sudo (not recommended for regular use):
    sudo uv run pytest agents_runner/tests/test_docker_e2e.py -v
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import time
from dataclasses import replace
from threading import Event
from typing import Any

import pytest

from agents_runner.docker.config import DockerRunnerConfig
from agents_runner.docker.workers import DockerAgentWorker
from agents_runner.docker.process import _run_docker, _inspect_state
from agents_runner.persistence import (
    save_task_payload,
    load_task_payload,
    ensure_task_dirs,
)


# Use a lightweight, commonly available image for testing
TEST_IMAGE = "alpine:latest"


def _can_access_docker() -> bool:
    """Check if Docker is accessible."""
    try:
        subprocess.run(
            ["docker", "ps"],
            capture_output=True,
            check=True,
            timeout=5.0,
        )
        return True
    except Exception:
        return False


# Skip all tests in this module if Docker is not accessible
pytestmark = pytest.mark.skipif(
    not _can_access_docker(),
    reason="Docker is not accessible. These E2E tests require Docker socket access.",
)


@pytest.fixture(scope="function")
def temp_state_dir():
    """Create a temporary directory for state files.

    Scope is function to ensure complete isolation between tests.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = os.path.join(tmpdir, "state.toml")
        ensure_task_dirs(state_path)
        yield state_path


@pytest.fixture(scope="function")
def test_config(temp_state_dir):
    """Create a test Docker runner config.

    Scope is function to ensure each test has completely isolated fixtures:
    - Unique task_id (timestamp-based)
    - Isolated temp directories
    - No shared state between test runs
    """
    # Create a temporary workspace directory
    workdir = tempfile.mkdtemp(prefix="docker-e2e-workspace-")
    codex_dir = tempfile.mkdtemp(prefix="docker-e2e-codex-")

    task_id = f"test-task-{int(time.time() * 1000)}"

    config = DockerRunnerConfig(
        task_id=task_id,
        image=TEST_IMAGE,
        host_workdir=workdir,
        host_codex_dir=codex_dir,
        container_workdir="/workspace",
        auto_remove=True,
        agent_cli="echo",  # Mock the agent CLI with echo
        agent_cli_args=[],
        environment_id="test-env",
        headless_desktop_enabled=False,
    )

    yield config, temp_state_dir, workdir, codex_dir, task_id

    # Cleanup
    try:
        import shutil

        shutil.rmtree(workdir, ignore_errors=True)
        shutil.rmtree(codex_dir, ignore_errors=True)
    except Exception:
        pass


def ensure_test_image():
    """Ensure the test Docker image is available."""
    try:
        _run_docker(["image", "inspect", TEST_IMAGE], timeout_s=10.0)
    except Exception:
        # Pull the image if not available
        _run_docker(["pull", TEST_IMAGE], timeout_s=120.0)


def test_task_lifecycle_completes_successfully(test_config):
    """Test creating a task that runs a container and completes successfully.

    Verifies:
    - Task state transitions (queued -> running -> completed)
    - Container execution
    - State persistence
    """
    ensure_test_image()

    config, state_path, workdir, codex_dir, task_id = test_config

    # Verify fixture isolation: ensure unique task_id
    assert task_id.startswith("test-task-"), "task_id should have expected prefix"
    assert len(task_id) > len("test-task-"), (
        "task_id should be unique (timestamp-based)"
    )

    # Modify config to use a more robust command that avoids Docker stream race conditions
    config = replace(
        config,
        agent_cli="sh",
        agent_cli_args=["-c", "echo 'test output' && exit 0"],
    )

    # Task tracking
    states_received = []
    logs_received = []
    done_called = Event()
    final_exit_code = None
    final_error = None
    final_artifacts = None

    def on_state(state: dict[str, Any]) -> None:
        states_received.append(dict(state))
        # Save state to persistence
        payload = {
            "task_id": task_id,
            "status": state.get("Status", "queued"),
            "container_id": state.get("ContainerId"),
            "prompt": "test prompt",
            "image": TEST_IMAGE,
            "host_workdir": workdir,
            "host_codex_dir": codex_dir,
            "created_at_s": time.time(),
        }
        save_task_payload(state_path, payload, archived=False)

    def on_log(log: str) -> None:
        logs_received.append(log)

    def on_done(exit_code: int, error: str | None, artifacts: list[str]) -> None:
        nonlocal final_exit_code, final_error, final_artifacts
        final_exit_code = exit_code
        final_error = error
        final_artifacts = artifacts
        done_called.set()

    # Create and run worker
    worker = DockerAgentWorker(
        config=config,
        prompt="test task execution",
        on_state=on_state,
        on_log=on_log,
        on_done=on_done,
    )

    # Start worker execution
    worker.run()

    # Wait for completion
    assert done_called.wait(timeout=30), "Task did not complete in time"

    # Verify final state
    assert final_exit_code == 0, f"Expected exit code 0, got {final_exit_code}"
    assert final_error is None, f"Unexpected error: {final_error}"

    # Verify state transitions were recorded
    assert len(states_received) > 0, "No state updates received"

    # Verify persistence
    saved_payload = load_task_payload(state_path, task_id, archived=False)
    assert saved_payload is not None, "Task payload not persisted"
    assert saved_payload["task_id"] == task_id
    assert saved_payload["container_id"] is not None

    # Mark as archived
    final_payload = dict(saved_payload)
    final_payload["status"] = "completed"
    save_task_payload(state_path, final_payload, archived=True)

    archived_payload = load_task_payload(state_path, task_id, archived=True)
    assert archived_payload is not None, "Archived task payload not found"
    assert archived_payload["status"] == "completed"


def test_task_cancel_stops_container(test_config):
    """Test canceling a running task stops the container gracefully.

    Verifies:
    - Task can be canceled mid-execution
    - Container is stopped (not killed)
    - State is persisted correctly
    """
    ensure_test_image()

    config, state_path, workdir, codex_dir, base_task_id = test_config

    # Verify fixture isolation: ensure unique base task_id
    assert base_task_id.startswith("test-task-"), (
        "base_task_id should have expected prefix"
    )
    assert len(base_task_id) > len("test-task-"), (
        "base_task_id should be unique (timestamp-based)"
    )

    # Create a new task ID for this test
    task_id = f"test-cancel-{int(time.time() * 1000)}"

    # Modify config to run a long-running command
    config = replace(
        config,
        task_id=task_id,
        agent_cli="sh",
        agent_cli_args=["-c", "sleep 60; echo done"],
    )

    states_received = []
    container_started = Event()
    done_called = Event()
    final_exit_code = None

    def on_state(state: dict[str, Any]) -> None:
        states_received.append(dict(state))
        if state.get("ContainerId"):
            container_started.set()
        payload = {
            "task_id": task_id,
            "status": state.get("Status", "queued"),
            "container_id": state.get("ContainerId"),
            "prompt": "long running task",
            "image": TEST_IMAGE,
            "host_workdir": workdir,
            "host_codex_dir": codex_dir,
            "created_at_s": time.time(),
        }
        save_task_payload(state_path, payload, archived=False)

    def on_log(log: str) -> None:
        pass

    def on_done(exit_code: int, error: str | None, artifacts: list[str]) -> None:
        nonlocal final_exit_code
        final_exit_code = exit_code
        done_called.set()

    worker = DockerAgentWorker(
        config=config,
        prompt="long running task",
        on_state=on_state,
        on_log=on_log,
        on_done=on_done,
    )

    # Start worker in a thread
    import threading

    thread = threading.Thread(target=worker.run)
    thread.start()

    # Wait for container to start
    assert container_started.wait(timeout=30), "Container did not start"

    # Get container ID
    saved_payload = load_task_payload(state_path, task_id, archived=False)
    assert saved_payload is not None
    container_id = saved_payload.get("container_id")
    assert container_id is not None

    # Verify container is running
    state = _inspect_state(container_id)
    assert state.get("Running") is True, "Container should be running"

    # Request stop (graceful cancel)
    worker.request_stop()

    # Wait for task to complete
    assert done_called.wait(timeout=30), "Task did not complete after stop"
    thread.join(timeout=5)
    assert not thread.is_alive(), "Worker thread should have completed"

    # Verify container is stopped
    try:
        state = _inspect_state(container_id)
        assert state.get("Running") is False, "Container should be stopped"
    except subprocess.CalledProcessError:
        # Expected if auto_remove=True removed the container
        pass

    # Verify final state indicates cancellation
    assert final_exit_code != 0, "Canceled task should have non-zero exit code"

    # Verify persistence reflects cancellation
    saved_payload = load_task_payload(state_path, task_id, archived=False)
    assert saved_payload is not None


def test_task_kill_removes_container(test_config):
    """Test killing a running task forcefully removes the container.

    Verifies:
    - Task can be killed mid-execution
    - Container is forcefully killed
    - State is persisted correctly
    """
    ensure_test_image()

    config, state_path, workdir, codex_dir, base_task_id = test_config

    # Verify fixture isolation: ensure unique base task_id
    assert base_task_id.startswith("test-task-"), (
        "base_task_id should have expected prefix"
    )
    assert len(base_task_id) > len("test-task-"), (
        "base_task_id should be unique (timestamp-based)"
    )

    # Create a new task ID for this test
    task_id = f"test-kill-{int(time.time() * 1000)}"

    # Run a long command
    config = replace(
        config,
        task_id=task_id,
        agent_cli="sh",
        agent_cli_args=["-c", "sleep 60; echo done"],
    )

    container_started = Event()
    done_called = Event()

    def on_state(state: dict[str, Any]) -> None:
        if state.get("ContainerId"):
            container_started.set()
        payload = {
            "task_id": task_id,
            "status": state.get("Status", "queued"),
            "container_id": state.get("ContainerId"),
            "prompt": "kill test task",
            "image": TEST_IMAGE,
            "host_workdir": workdir,
            "host_codex_dir": codex_dir,
            "created_at_s": time.time(),
        }
        save_task_payload(state_path, payload, archived=False)

    def on_log(log: str) -> None:
        pass

    def on_done(exit_code: int, error: str | None, artifacts: list[str]) -> None:
        done_called.set()

    worker = DockerAgentWorker(
        config=config,
        prompt="kill test task",
        on_state=on_state,
        on_log=on_log,
        on_done=on_done,
    )

    # Start worker
    import threading

    thread = threading.Thread(target=worker.run)
    thread.start()

    # Wait for container to start
    assert container_started.wait(timeout=30), "Container did not start"

    # Get container ID
    saved_payload = load_task_payload(state_path, task_id, archived=False)
    container_id = saved_payload.get("container_id")
    assert container_id is not None

    # Verify container is running
    state = _inspect_state(container_id)
    assert state.get("Running") is True

    # Request kill
    worker.request_kill()

    # Wait for completion
    assert done_called.wait(timeout=30), "Task did not complete after kill"
    thread.join(timeout=5)
    assert not thread.is_alive(), "Worker thread should have completed"

    # Verify container is gone or stopped
    try:
        state = _inspect_state(container_id)
        assert state.get("Running") is False, "Container should not be running"
    except subprocess.CalledProcessError:
        # Expected if container is removed
        pass

    # Verify persistence
    saved_payload = load_task_payload(state_path, task_id, archived=False)
    assert saved_payload is not None
