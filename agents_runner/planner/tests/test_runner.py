"""Tests for runner module."""

from pathlib import Path

import pytest

from agents_runner.planner.docker_adapter import DockerAdapter, ExecutionResult
from agents_runner.planner.models import (
    ArtifactSpec,
    DockerSpec,
    ExecSpec,
    MountSpec,
    RunPlan,
)
from agents_runner.planner.runner import execute_plan


class FakeDockerAdapter(DockerAdapter):
    """Fake Docker adapter for testing without real Docker.

    Records all method calls and their arguments for verification.
    Can be configured to simulate success or failure at any phase.
    """

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple]] = []
        self.pull_should_fail = False
        self.start_should_fail = False
        self.ready_should_fail = False
        self.exec_should_fail = False
        self.copy_should_fail = False
        self.exec_exit_code = 0
        self.exec_stdout = b"test output"
        self.exec_stderr = b""

    def pull_image(self, image: str, timeout: int) -> None:
        """Record pull_image call."""
        self.calls.append(("pull_image", (image, timeout)))
        if self.pull_should_fail:
            raise RuntimeError("Simulated pull failure")

    def start_container(self, spec: DockerSpec) -> str:
        """Record start_container call."""
        self.calls.append(("start_container", (spec,)))
        if self.start_should_fail:
            raise RuntimeError("Simulated start failure")
        return "fake-container-id"

    def wait_ready(self, container_id: str, timeout: int) -> None:
        """Record wait_ready call."""
        self.calls.append(("wait_ready", (container_id, timeout)))
        if self.ready_should_fail:
            raise RuntimeError("Simulated ready failure")

    def exec_run(self, container_id: str, exec_spec: ExecSpec) -> ExecutionResult:
        """Record exec_run call."""
        self.calls.append(("exec_run", (container_id, exec_spec)))
        if self.exec_should_fail:
            raise RuntimeError("Simulated exec failure")
        return ExecutionResult(
            exit_code=self.exec_exit_code,
            stdout=self.exec_stdout,
            stderr=self.exec_stderr,
        )

    def copy_from(self, container_id: str, src: Path, dst: Path) -> None:
        """Record copy_from call."""
        self.calls.append(("copy_from", (container_id, src, dst)))
        if self.copy_should_fail:
            raise RuntimeError("Simulated copy failure")

    def stop_remove(self, container_id: str) -> None:
        """Record stop_remove call."""
        self.calls.append(("stop_remove", (container_id,)))


def _create_test_plan(
    interactive: bool = False,
    with_artifacts: bool = True,
) -> RunPlan:
    """Create a test RunPlan."""
    docker = DockerSpec(
        image="python:3.13",
        workdir=Path("/workspace"),
        mounts=[
            MountSpec(src=Path("/tmp/host"), dst=Path("/workspace"), mode="rw"),
            MountSpec(src=Path("/tmp/config"), dst=Path("/root/.codex"), mode="rw"),
        ],
        env={"TEST": "value"},
    )

    exec_spec = ExecSpec(
        argv=["codex", "--prompt", "test"],
        cwd=Path("/workspace"),
        tty=interactive,
        stdin=interactive,
    )

    artifacts = ArtifactSpec()
    if with_artifacts:
        # Artifacts should be under a mounted directory (workspace) to be collectable
        artifacts = ArtifactSpec(
            finish_file=Path("/workspace/agents-artifacts/FINISH"),
            output_file=Path("/workspace/agents-artifacts/agent-output.md"),
        )

    return RunPlan(
        interactive=interactive,
        docker=docker,
        prompt_text="test prompt",
        exec_spec=exec_spec,
        artifacts=artifacts,
    )


def test_execute_plan_success_flow() -> None:
    """Test successful execution flow through all phases."""
    adapter = FakeDockerAdapter()
    plan = _create_test_plan()

    result = execute_plan(plan, adapter)

    # Verify execution succeeded
    assert result.exit_code == 0
    assert result.stdout == b"test output"

    # Verify correct call sequence
    call_names = [call[0] for call in adapter.calls]
    assert call_names == [
        "pull_image",
        "start_container",
        "wait_ready",
        "exec_run",
        "copy_from",  # finish file
        "copy_from",  # output file
        "stop_remove",
    ]


def test_execute_plan_pull_image_called_correctly() -> None:
    """Test pull_image is called with correct parameters."""
    adapter = FakeDockerAdapter()
    plan = _create_test_plan()

    execute_plan(plan, adapter)

    pull_calls = [call for call in adapter.calls if call[0] == "pull_image"]
    assert len(pull_calls) == 1
    image, timeout = pull_calls[0][1]
    assert image == "python:3.13"
    assert timeout > 0


def test_execute_plan_start_container_called_correctly() -> None:
    """Test start_container is called with correct DockerSpec."""
    adapter = FakeDockerAdapter()
    plan = _create_test_plan()

    execute_plan(plan, adapter)

    start_calls = [call for call in adapter.calls if call[0] == "start_container"]
    assert len(start_calls) == 1
    spec = start_calls[0][1][0]
    assert spec.image == "python:3.13"
    assert spec.workdir == Path("/workspace")


def test_execute_plan_wait_ready_called_correctly() -> None:
    """Test wait_ready is called with container ID and timeout."""
    adapter = FakeDockerAdapter()
    plan = _create_test_plan()

    execute_plan(plan, adapter)

    ready_calls = [call for call in adapter.calls if call[0] == "wait_ready"]
    assert len(ready_calls) == 1
    container_id, timeout = ready_calls[0][1]
    assert container_id == "fake-container-id"
    assert timeout > 0


def test_execute_plan_exec_run_called_correctly() -> None:
    """Test exec_run is called with container ID and ExecSpec."""
    adapter = FakeDockerAdapter()
    plan = _create_test_plan()

    execute_plan(plan, adapter)

    exec_calls = [call for call in adapter.calls if call[0] == "exec_run"]
    assert len(exec_calls) == 1
    container_id, exec_spec = exec_calls[0][1]
    assert container_id == "fake-container-id"
    assert exec_spec.argv == ["codex", "--prompt", "test"]


def test_execute_plan_artifacts_collected() -> None:
    """Test artifacts are copied from container to host."""
    adapter = FakeDockerAdapter()
    plan = _create_test_plan(with_artifacts=True)

    execute_plan(plan, adapter)

    copy_calls = [call for call in adapter.calls if call[0] == "copy_from"]
    assert len(copy_calls) == 2

    # Verify finish file copy
    container_id, src, dst = copy_calls[0][1]
    assert container_id == "fake-container-id"
    assert src == Path("/workspace/agents-artifacts/FINISH")
    assert dst == Path("/tmp/host/agents-artifacts/FINISH")

    # Verify output file copy
    container_id, src, dst = copy_calls[1][1]
    assert container_id == "fake-container-id"
    assert src == Path("/workspace/agents-artifacts/agent-output.md")
    assert dst == Path("/tmp/host/agents-artifacts/agent-output.md")


def test_execute_plan_no_artifacts() -> None:
    """Test execution without artifact collection."""
    adapter = FakeDockerAdapter()
    plan = _create_test_plan(with_artifacts=False)

    execute_plan(plan, adapter)

    # No copy_from calls should be made
    copy_calls = [call for call in adapter.calls if call[0] == "copy_from"]
    assert len(copy_calls) == 0


def test_execute_plan_cleanup_always_called() -> None:
    """Test container cleanup happens even on exec failure."""
    adapter = FakeDockerAdapter()
    adapter.exec_should_fail = True
    plan = _create_test_plan()

    with pytest.raises(RuntimeError, match="Simulated exec failure"):
        execute_plan(plan, adapter)

    # Verify cleanup was called
    cleanup_calls = [call for call in adapter.calls if call[0] == "stop_remove"]
    assert len(cleanup_calls) == 1
    container_id = cleanup_calls[0][1][0]
    assert container_id == "fake-container-id"


def test_execute_plan_cleanup_on_pull_failure() -> None:
    """Test cleanup doesn't error when container was never started."""
    adapter = FakeDockerAdapter()
    adapter.pull_should_fail = True
    plan = _create_test_plan()

    with pytest.raises(RuntimeError, match="Simulated pull failure"):
        execute_plan(plan, adapter)

    # No cleanup should be called since container was never created
    cleanup_calls = [call for call in adapter.calls if call[0] == "stop_remove"]
    assert len(cleanup_calls) == 0


def test_execute_plan_cleanup_on_start_failure() -> None:
    """Test cleanup doesn't error when start fails."""
    adapter = FakeDockerAdapter()
    adapter.start_should_fail = True
    plan = _create_test_plan()

    with pytest.raises(RuntimeError, match="Simulated start failure"):
        execute_plan(plan, adapter)

    # No cleanup should be called since start failed
    cleanup_calls = [call for call in adapter.calls if call[0] == "stop_remove"]
    assert len(cleanup_calls) == 0


def test_execute_plan_cleanup_on_ready_failure() -> None:
    """Test cleanup is called when ready phase fails."""
    adapter = FakeDockerAdapter()
    adapter.ready_should_fail = True
    plan = _create_test_plan()

    with pytest.raises(RuntimeError, match="Simulated ready failure"):
        execute_plan(plan, adapter)

    # Cleanup should be called since container was started
    cleanup_calls = [call for call in adapter.calls if call[0] == "stop_remove"]
    assert len(cleanup_calls) == 1


def test_execute_plan_missing_artifact_ignored() -> None:
    """Test missing artifacts don't cause execution to fail."""
    adapter = FakeDockerAdapter()
    adapter.copy_should_fail = True
    plan = _create_test_plan(with_artifacts=True)

    # Should not raise even though copy fails
    result = execute_plan(plan, adapter)

    assert result.exit_code == 0
    # Cleanup should still happen
    cleanup_calls = [call for call in adapter.calls if call[0] == "stop_remove"]
    assert len(cleanup_calls) == 1


def test_execute_plan_returns_correct_result() -> None:
    """Test execution result is properly returned."""
    adapter = FakeDockerAdapter()
    adapter.exec_exit_code = 42
    adapter.exec_stdout = b"custom output"
    adapter.exec_stderr = b"custom error"
    plan = _create_test_plan()

    result = execute_plan(plan, adapter)

    assert result.exit_code == 42
    assert result.stdout == b"custom output"
    assert result.stderr == b"custom error"


def test_execute_plan_interactive_mode() -> None:
    """Test interactive mode execution."""
    adapter = FakeDockerAdapter()
    plan = _create_test_plan(interactive=True)

    execute_plan(plan, adapter)

    # Verify exec spec has interactive settings
    exec_calls = [call for call in adapter.calls if call[0] == "exec_run"]
    assert len(exec_calls) == 1
    _, exec_spec = exec_calls[0][1]
    assert exec_spec.tty is True
    assert exec_spec.stdin is True


def test_execute_plan_noninteractive_mode() -> None:
    """Test non-interactive mode execution."""
    adapter = FakeDockerAdapter()
    plan = _create_test_plan(interactive=False)

    execute_plan(plan, adapter)

    # Verify exec spec has non-interactive settings
    exec_calls = [call for call in adapter.calls if call[0] == "exec_run"]
    assert len(exec_calls) == 1
    _, exec_spec = exec_calls[0][1]
    assert exec_spec.tty is False
    assert exec_spec.stdin is False
