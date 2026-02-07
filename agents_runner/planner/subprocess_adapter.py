"""Concrete Docker adapter implementation using subprocess.

This module provides a real implementation of DockerAdapter that executes
docker commands via subprocess. Used for production runs.
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

from agents_runner.planner.docker_adapter import DockerAdapter, ExecutionResult
from agents_runner.planner.models import DockerSpec, ExecSpec


class SubprocessDockerAdapter(DockerAdapter):
    """Docker adapter that executes commands via subprocess.

    This is the production implementation used for actual container runs.
    """

    def pull_image(self, image: str, timeout: int) -> None:
        """Pull a Docker image using docker pull.

        Args:
            image: Image reference to pull.
            timeout: Maximum time to wait in seconds.

        Raises:
            TimeoutError: If pull exceeds timeout.
            RuntimeError: If pull fails.
        """
        cmd = ["docker", "pull", image]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            if result.returncode != 0:
                raise RuntimeError(f"Failed to pull image {image}: {result.stderr}")
        except subprocess.TimeoutExpired as e:
            raise TimeoutError(f"Image pull timed out after {timeout}s: {image}") from e

    def start_container(self, spec: DockerSpec) -> str:
        """Start a container with keepalive command.

        Args:
            spec: Docker container configuration.

        Returns:
            Container ID.

        Raises:
            RuntimeError: If container fails to start.
        """
        cmd = ["docker", "run", "-d"]

        # Add container name if specified
        if spec.container_name:
            cmd.extend(["--name", spec.container_name])

        # Add working directory
        cmd.extend(["-w", str(spec.workdir)])

        # Add environment variables
        for key, value in spec.env.items():
            cmd.extend(["-e", f"{key}={value}"])

        # Add volume mounts
        for mount in spec.mounts:
            mount_str = f"{mount.src}:{mount.dst}"
            if mount.mode == "ro":
                mount_str += ":ro"
            cmd.extend(["-v", mount_str])

        # Add port mappings
        for port in spec.ports:
            cmd.extend(["-p", port])

        # Add image
        cmd.append(spec.image)

        # Add keepalive command
        cmd.extend(spec.keepalive_argv)

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            raise RuntimeError(f"Failed to start container: {result.stderr}")

        # Return container ID (strip whitespace)
        return result.stdout.strip()

    def wait_ready(self, container_id: str, timeout: int) -> None:
        """Wait for container to reach running state.

        Args:
            container_id: Container to wait for.
            timeout: Maximum time to wait in seconds.

        Raises:
            TimeoutError: If container doesn't become ready in time.
            RuntimeError: If container fails or exits unexpectedly.
        """
        start_time = time.time()
        poll_interval = 0.5  # Poll every 500ms

        while True:
            # Check elapsed time
            elapsed = time.time() - start_time
            if elapsed > timeout:
                raise TimeoutError(f"Container did not become ready within {timeout}s")

            # Check container status
            cmd = ["docker", "inspect", container_id, "--format", "{{json .State}}"]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode != 0:
                raise RuntimeError(f"Failed to inspect container: {result.stderr}")

            try:
                state = json.loads(result.stdout)
            except json.JSONDecodeError as e:
                raise RuntimeError(
                    f"Failed to parse container state: {result.stdout}"
                ) from e

            # Check if running
            if state.get("Status") == "running":
                return

            # Check if exited/dead
            if state.get("Status") in ("exited", "dead"):
                exit_code = state.get("ExitCode", "unknown")
                raise RuntimeError(
                    f"Container exited unexpectedly with code {exit_code}"
                )

            # Sleep before next poll
            time.sleep(poll_interval)

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
        cmd = ["docker", "exec"]

        # Add TTY flag if requested
        if exec_spec.tty:
            cmd.append("-t")

        # Add interactive flag if stdin requested
        if exec_spec.stdin:
            cmd.append("-i")

        # Add working directory if specified
        if exec_spec.cwd is not None:
            cmd.extend(["-w", str(exec_spec.cwd)])

        # Add environment variables
        for key, value in exec_spec.env.items():
            cmd.extend(["-e", f"{key}={value}"])

        # Add container ID
        cmd.append(container_id)

        # Add command and arguments
        cmd.extend(exec_spec.argv)

        result = subprocess.run(
            cmd,
            capture_output=True,
            check=False,
        )

        return ExecutionResult(
            exit_code=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
        )

    def copy_from(self, container_id: str, src: Path, dst: Path) -> None:
        """Copy a file from container to host.

        Args:
            container_id: Container to copy from.
            src: Source path in container (absolute).
            dst: Destination path on host (absolute).

        Raises:
            RuntimeError: If copy fails.
        """
        # Ensure destination directory exists
        dst.parent.mkdir(parents=True, exist_ok=True)

        # docker cp container_id:src dst
        container_src = f"{container_id}:{src}"
        cmd = ["docker", "cp", container_src, str(dst)]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            raise RuntimeError(f"Failed to copy {src} from container: {result.stderr}")

    def stop_remove(self, container_id: str) -> None:
        """Stop and remove a container.

        Args:
            container_id: Container to stop and remove.

        Note:
            Does not raise if container is already stopped/removed.
        """
        # Stop container (ignore errors if already stopped)
        subprocess.run(
            ["docker", "stop", container_id],
            capture_output=True,
            check=False,
        )

        # Remove container (ignore errors if already removed)
        subprocess.run(
            ["docker", "rm", container_id],
            capture_output=True,
            check=False,
        )

    def get_port_mapping(self, container_id: str, container_port: str) -> str | None:
        """Get the host port mapping for a container port.

        Args:
            container_id: Container to inspect.
            container_port: Container port in format "PORT/PROTOCOL" (e.g., "6080/tcp").

        Returns:
            Host port string (e.g., "32768") or None if not mapped.

        Raises:
            RuntimeError: If port inspection fails.
        """
        cmd = ["docker", "port", container_id, container_port]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            raise RuntimeError(
                f"Failed to get port mapping for {container_port}: {result.stderr}"
            )

        # Parse output like "127.0.0.1:32768"
        mapping = result.stdout.strip()
        if not mapping:
            return None

        # Get first line if multiple
        first_line = mapping.splitlines()[0] if mapping else ""
        if not first_line or ":" not in first_line:
            return None

        # Extract port number from "127.0.0.1:32768"
        host_port = first_line.rsplit(":", 1)[-1].strip()
        return host_port if host_port.isdigit() else None
