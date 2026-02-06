"""Docker runner implementation following standardized flow.

This module implements the execute_plan function that orchestrates the
complete lifecycle of a container run: pull, start, wait, exec, collect
artifacts, and cleanup.
"""

from __future__ import annotations

from pathlib import Path

from agents_runner.planner.docker_adapter import DockerAdapter, ExecutionResult
from agents_runner.planner.models import RunPlan


def execute_plan(plan: RunPlan, adapter: DockerAdapter) -> ExecutionResult:
    """Execute a run plan using the provided Docker adapter.

    This function follows the standardized flow:
    1. Pull image
    2. Start container with keepalive command
    3. Wait for ready state
    4. Execute command via docker exec
    5. Collect artifacts
    6. Stop and remove container

    Args:
        plan: Fully-resolved run plan.
        adapter: Docker adapter for container operations.

    Returns:
        Execution result from the agent command.

    Raises:
        TimeoutError: If any phase exceeds its timeout.
        RuntimeError: If any phase fails.

    Note:
        Container is always stopped and removed, even if execution fails.
    """
    container_id: str | None = None

    try:
        # Phase 1: Pull image
        # Use pull timeout from plan's docker spec if available, else default
        pull_timeout = getattr(plan.docker, "pull_timeout", 60 * 15)
        adapter.pull_image(plan.docker.image, timeout=pull_timeout)

        # Phase 2: Start container with keepalive command
        container_id = adapter.start_container(plan.docker)

        # Phase 3: Wait for ready state
        # Use ready timeout from plan's docker spec if available, else default
        ready_timeout = getattr(plan.docker, "ready_timeout", 60 * 5)
        adapter.wait_ready(container_id, timeout=ready_timeout)

        # Phase 4: Execute command via docker exec
        result = adapter.exec_run(container_id, plan.exec_spec)

        # Phase 5: Collect artifacts
        _collect_artifacts(adapter, container_id, plan)

        return result

    finally:
        # Phase 6: Stop and remove container (always cleanup)
        if container_id is not None:
            adapter.stop_remove(container_id)


def _collect_artifacts(
    adapter: DockerAdapter, container_id: str, plan: RunPlan
) -> None:
    """Collect artifacts from container according to plan.

    Args:
        adapter: Docker adapter for copy operations.
        container_id: Container to copy from.
        plan: Run plan with artifact specifications.

    Note:
        Silently skips artifacts that don't exist in the container.
    """
    # Copy finish file if specified
    if plan.artifacts.finish_file is not None:
        src = plan.artifacts.finish_file
        # Place finish file in host workdir (extract from docker mounts)
        dst = _resolve_host_path(plan, src)
        if dst is not None:
            try:
                adapter.copy_from(container_id, src, dst)
            except RuntimeError:
                # Finish file may not exist if run failed early
                pass

    # Copy output file if specified
    if plan.artifacts.output_file is not None:
        src = plan.artifacts.output_file
        dst = _resolve_host_path(plan, src)
        if dst is not None:
            try:
                adapter.copy_from(container_id, src, dst)
            except RuntimeError:
                # Output file may not exist if run failed early
                pass


def _resolve_host_path(plan: RunPlan, container_path: Path) -> Path | None:
    """Resolve a container path to its corresponding host path.

    Args:
        plan: Run plan with mount specifications.
        container_path: Path in the container.

    Returns:
        Corresponding host path, or None if not under any mount.

    Note:
        Returns None if container_path is not under any mounted directory.
    """
    for mount in plan.docker.mounts:
        # Check if container_path is under this mount's destination
        try:
            relative = container_path.relative_to(mount.dst)
            # Map back to host path
            return mount.src / relative
        except ValueError:
            # Not under this mount, try next
            continue

    # No mount found for this path
    return None
