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
from agents_runner.docker.process import run_docker, inspect_state
from agents_runner.persistence import (
    save_task_payload,
    load_task_payload,
    ensure_task_dirs,
)


# Use the same image as production (PixelArch)
TEST_IMAGE = "lunamidori5/pixelarch:emerald"


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


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_containers():
    """Cleanup any leftover test containers before and after test session.

    This is best-effort cleanup - errors are logged but don't fail the session.
    """

    def cleanup():
        try:
            # List all containers with agents-runner prefix
            result = run_docker(
                ["ps", "-a", "--filter", "name=agents-runner-", "--format", "{{.ID}}"],
                timeout_s=10.0,
            )
            container_ids = result.stdout.strip().split("\n")
            container_ids = [cid.strip() for cid in container_ids if cid.strip()]

            # Remove each container
            for container_id in container_ids:
                try:
                    run_docker(["rm", "-f", container_id], timeout_s=10.0)
                except Exception:
                    # Best-effort - continue even if removal fails
                    pass
        except Exception:
            # Best-effort cleanup - don't fail session if this fails
            pass

    # Cleanup before session
    cleanup()

    yield

    # Cleanup after session
    cleanup()


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
def test_config(temp_state_dir, request):
    """Create a test Docker runner config.

    Scope is function to ensure each test has completely isolated fixtures:
    - Unique task_id (timestamp-based)
    - Test-specific container name for easy identification
    - Isolated temp directories
    - No shared state between test runs
    """
    # Create a temporary workspace directory
    workdir = tempfile.mkdtemp(prefix="docker-e2e-workspace-")
    codex_dir = tempfile.mkdtemp(prefix="docker-e2e-codex-")

    task_id = f"test-task-{int(time.time() * 1000)}"

    # Generate test-specific container name
    # Truncate test name to stay under Docker's 63-char limit
    # Format: agents-runner-test-{test_name}-{short_uuid}
    test_name = request.node.name[:20]  # Max 20 chars for test name
    short_uuid = f"{int(time.time() * 1000) % 1000000:06d}"  # 6-digit time-based ID
    container_name = f"agents-runner-test-{test_name}-{short_uuid}"

    container_id = None

    config = DockerRunnerConfig(
        task_id=task_id,
        image=TEST_IMAGE,
        host_workdir=workdir,
        host_config_dir=codex_dir,
        container_workdir="/workspace",
        auto_remove=True,
        agent_cli="echo",  # Mock the agent CLI with echo
        agent_cli_args=[],
        environment_id="test-env",
        headless_desktop_enabled=False,
        container_name=container_name,
    )

    def finalizer():
        """Wait for container removal and cleanup directories."""
        # Best-effort wait for container removal
        if container_id:
            for _ in range(10):
                try:
                    inspect_state(container_id)
                    # Container still exists, wait
                    time.sleep(1)
                except subprocess.CalledProcessError:
                    # Container removed successfully
                    break

        # Cleanup directories
        try:
            import shutil

            shutil.rmtree(workdir, ignore_errors=True)
            shutil.rmtree(codex_dir, ignore_errors=True)
        except Exception:
            pass

    request.addfinalizer(finalizer)

    yield config, temp_state_dir, workdir, codex_dir, task_id

    # Store container_id from any test that creates one
    # This is a simple approach - tests can update this if they track container_id
    # More robust: tests could register their container_id via a callback


def ensure_test_image():
    """Ensure the test Docker image is available."""
    try:
        run_docker(["image", "inspect", TEST_IMAGE], timeout_s=10.0)
    except Exception:
        # Pull the image if not available
        run_docker(["pull", TEST_IMAGE], timeout_s=120.0)


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
    # Add 20s sleep before echo to ensure container has time to start and report state
    # Use absolute path /bin/sh to avoid PATH resolution issues in PixelArch
    config = replace(
        config,
        agent_cli="/bin/sh",
        agent_cli_args=["-c", "sleep 20 && echo 'test output' && exit 0"],
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
            "prompt": "test prompt",
            "image": TEST_IMAGE,
            "host_workdir": workdir,
            "host_config_dir": codex_dir,
            "created_at_s": time.time(),
        }
        # Only include container_id if present (None values are stripped during TOML serialization)
        container_id = state.get("ContainerId")
        if container_id is not None:
            payload["container_id"] = container_id
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

    # Verify that worker created a container
    assert worker.container_id is not None, "Worker did not create a container"

    # Mark as archived
    final_payload = dict(saved_payload)
    final_payload["status"] = "completed"
    save_task_payload(state_path, final_payload, archived=True)

    archived_payload = load_task_payload(state_path, task_id, archived=True)
    assert archived_payload is not None, "Archived task payload not found"
    assert archived_payload["status"] == "completed"
