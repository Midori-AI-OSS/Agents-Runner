"""Run planner that converts RunRequest to RunPlan.

This module provides the core planning logic for converting user intent
(RunRequest) into a fully-resolved executable plan (RunPlan). The planner
is a pure function with no side effects.
"""

from __future__ import annotations

from pathlib import Path

from agents_runner.agent_cli import (
    CONTAINER_WORKDIR,
    build_noninteractive_cmd,
    container_config_dir,
)
from agents_runner.planner.models import (
    ArtifactSpec,
    DockerSpec,
    ExecSpec,
    MountSpec,
    RunPlan,
    RunRequest,
)

# Interactive run guardrail prefix
INTERACTIVE_PREFIX = (
    "do not take action, just review the needed files and check your preflight "
    "if the repo has those and then standby"
)

# Default artifact paths
FINISH_FILE = Path("/tmp/agents-artifacts/FINISH")
OUTPUT_FILE = Path("/tmp/agents-artifacts/agent-output.md")


def plan_run(request: RunRequest) -> RunPlan:
    """Convert a RunRequest into a fully-resolved RunPlan.

    This function transforms user intent (RunRequest) into a concrete execution
    plan (RunPlan) by:
    1. Converting EnvironmentSpec to DockerSpec (image, mounts, env vars)
    2. Building ExecSpec for the agent command
    3. Composing the prompt text (with interactive prefix if needed)
    4. Setting up artifact collection paths

    The function is pure and has no side effects (no subprocess, filesystem,
    or network calls).

    Args:
        request: User intent for an agent run.

    Returns:
        A fully-resolved RunPlan ready for execution.
    """
    # Build Docker configuration
    docker = _build_docker_spec(request)

    # Compose prompt text
    prompt_text = _compose_prompt(request)

    # Build execution specification
    exec_spec = _build_exec_spec(request, prompt_text)

    # Set up artifact collection
    artifacts = ArtifactSpec(
        finish_file=FINISH_FILE,
        output_file=OUTPUT_FILE,
    )

    return RunPlan(
        interactive=request.interactive,
        docker=docker,
        prompt_text=prompt_text,
        exec_spec=exec_spec,
        artifacts=artifacts,
    )


def _build_docker_spec(request: RunRequest) -> DockerSpec:
    """Build Docker configuration from RunRequest.

    Args:
        request: User intent for an agent run.

    Returns:
        DockerSpec with image, mounts, env vars, and workdir.
    """
    env = request.environment

    # Start with workspace mount
    mounts = [
        MountSpec(
            src=request.host_workdir,
            dst=Path(CONTAINER_WORKDIR),
            mode="rw",
        )
    ]

    # Add config directory mount
    config_dst = Path(container_config_dir(request.system_name))
    mounts.append(
        MountSpec(
            src=request.host_config_dir,
            dst=config_dst,
            mode="rw",
        )
    )

    # Parse and add extra mounts from environment
    for mount_str in env.extra_mounts:
        mount_str = mount_str.strip()
        if not mount_str:
            continue

        # Parse mount string: "src:dst" or "src:dst:mode"
        parts = mount_str.split(":")
        if len(parts) < 2:
            continue

        src = Path(parts[0]).expanduser()
        dst = Path(parts[1])
        mode = parts[2] if len(parts) > 2 else "rw"

        # Validate mode
        if mode not in ("ro", "rw"):
            mode = "rw"

        # Only add if paths are absolute
        if src.is_absolute() and dst.is_absolute():
            mounts.append(MountSpec(src=src, dst=dst, mode=mode))  # type: ignore

    # Build environment variables
    env_vars = dict(env.env_vars)

    # Add agent-specific environment variables if needed
    # (Future: add GH_TOKEN, etc. if gh_context_enabled)

    return DockerSpec(
        image=env.image,
        workdir=Path(CONTAINER_WORKDIR),
        mounts=mounts,
        env=env_vars,
    )


def _compose_prompt(request: RunRequest) -> str:
    """Compose the prompt text for the agent.

    For interactive runs, prepends the guardrail prefix to prevent
    the agent from taking action before user review.

    Args:
        request: User intent for an agent run.

    Returns:
        Composed prompt text.
    """
    prompt = request.prompt.strip()

    if request.interactive:
        return f"{INTERACTIVE_PREFIX}\n\n{prompt}"

    return prompt


def _build_exec_spec(request: RunRequest, prompt_text: str) -> ExecSpec:
    """Build execution specification for the agent command.

    Args:
        request: User intent for an agent run.
        prompt_text: Composed prompt text (may include interactive prefix).

    Returns:
        ExecSpec with command, args, and execution settings.
    """
    # Build command arguments using existing agent_cli logic
    argv = build_noninteractive_cmd(
        agent=request.system_name,
        prompt=prompt_text,
        host_workdir=str(request.host_workdir),
        container_workdir=CONTAINER_WORKDIR,
        agent_cli_args=request.extra_cli_args,
    )

    return ExecSpec(
        argv=argv,
        cwd=Path(CONTAINER_WORKDIR),
        tty=request.interactive,
        stdin=request.interactive,
    )
