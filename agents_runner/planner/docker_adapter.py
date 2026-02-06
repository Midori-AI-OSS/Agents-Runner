"""Docker adapter interface for testable container operations.

This module defines an abstract interface for Docker operations, allowing
the runner to be tested without requiring an actual Docker daemon. Concrete
implementations use subprocess to execute docker commands.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from agents_runner.planner.models import DockerSpec, ExecSpec


class ExecutionResult:
    """Result of a docker exec command.

    Attributes:
        exit_code: Process exit code.
        stdout: Standard output as bytes.
        stderr: Standard error as bytes.
    """

    def __init__(self, exit_code: int, stdout: bytes, stderr: bytes) -> None:
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr


class DockerAdapter(ABC):
    """Abstract interface for Docker container operations.

    This interface isolates Docker calls behind a testable boundary,
    allowing tests to verify call sequences and arguments without
    requiring an actual Docker daemon.
    """

    @abstractmethod
    def pull_image(self, image: str, timeout: int) -> None:
        """Pull a Docker image.

        Args:
            image: Image reference to pull (e.g., "python:3.13").
            timeout: Maximum time to wait in seconds.

        Raises:
            TimeoutError: If pull exceeds timeout.
            RuntimeError: If pull fails.
        """
        ...

    @abstractmethod
    def start_container(self, spec: DockerSpec) -> str:
        """Start a container with a keepalive command.

        Args:
            spec: Docker container configuration.

        Returns:
            Container ID.

        Raises:
            RuntimeError: If container fails to start.
        """
        ...

    @abstractmethod
    def wait_ready(self, container_id: str, timeout: int) -> None:
        """Wait for container to reach running state.

        Args:
            container_id: Container to wait for.
            timeout: Maximum time to wait in seconds.

        Raises:
            TimeoutError: If container doesn't become ready in time.
            RuntimeError: If container fails or exits unexpectedly.
        """
        ...

    @abstractmethod
    def exec_run(self, container_id: str, exec_spec: ExecSpec) -> ExecutionResult:
        """Execute a command in the container.

        Args:
            container_id: Container to execute in.
            exec_spec: Execution specification.

        Returns:
            Execution result with exit code and output.

        Raises:
            RuntimeError: If exec fails to start.
        """
        ...

    @abstractmethod
    def copy_from(self, container_id: str, src: Path, dst: Path) -> None:
        """Copy a file from container to host.

        Args:
            container_id: Container to copy from.
            src: Source path in container (absolute).
            dst: Destination path on host (absolute).

        Raises:
            RuntimeError: If copy fails.
        """
        ...

    @abstractmethod
    def stop_remove(self, container_id: str) -> None:
        """Stop and remove a container.

        Args:
            container_id: Container to stop and remove.

        Note:
            Should not raise if container is already stopped/removed.
        """
        ...
