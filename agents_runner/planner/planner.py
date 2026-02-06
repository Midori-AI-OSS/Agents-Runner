"""Run planner that converts RunRequest to RunPlan.

This module provides the core planning logic for converting user intent
(RunRequest) into a fully-resolved executable plan (RunPlan). The planner
queries the agent system plugin registry to generate execution plans.
"""

from __future__ import annotations

from pathlib import Path

from agents_runner.agent_cli import CONTAINER_WORKDIR
from agents_runner.agent_systems.models import AgentSystemContext, AgentSystemRequest
from agents_runner.agent_systems.registry import get_plugin
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
    1. Retrieving the agent system plugin by name
    2. Building AgentSystemContext from the request
    3. Calling plugin.plan() to get the AgentSystemPlan
    4. Converting AgentSystemPlan to RunPlan with full Docker configuration

    Args:
        request: User intent for an agent run.

    Returns:
        A fully-resolved RunPlan ready for execution.

    Raises:
        ValueError: If the requested agent system is not registered.
    """
    # Get plugin from registry
    plugin = get_plugin(request.system_name)
    if plugin is None:
        raise ValueError(
            f"Agent system '{request.system_name}' is not registered. "
            f"Available systems can be listed via the registry."
        )

    # Check if interactive mode is supported
    if request.interactive and not plugin.capabilities.supports_interactive:
        raise ValueError(
            f"Agent system '{request.system_name}' does not support interactive mode"
        )

    # Compose prompt text (with interactive prefix if needed)
    prompt_text = _compose_prompt(request)

    # Build agent system context
    context = AgentSystemContext(
        workspace_host=request.host_workdir,
        workspace_container=Path(CONTAINER_WORKDIR),
        config_host=request.host_config_dir,
        config_container=Path(CONTAINER_WORKDIR).parent / ".config",
        extra_cli_args=request.extra_cli_args,
    )

    # Build agent system request
    agent_request = AgentSystemRequest(
        system_name=request.system_name,
        interactive=request.interactive,
        prompt=prompt_text,
        context=context,
    )

    # Get execution plan from plugin
    agent_plan = plugin.plan(agent_request)

    # Build Docker configuration
    docker = _build_docker_spec(request, agent_plan)

    # Convert agent_systems.models.ExecSpec to planner.models.ExecSpec
    exec_spec = ExecSpec(
        argv=agent_plan.exec_spec.argv,
        cwd=agent_plan.exec_spec.cwd,
        env=agent_plan.exec_spec.env,
        tty=agent_plan.exec_spec.tty,
        stdin=agent_plan.exec_spec.stdin,
    )

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


def _build_docker_spec(request: RunRequest, agent_plan) -> DockerSpec:  # type: ignore
    """Build Docker configuration from RunRequest and AgentSystemPlan.

    Combines:
    - Base environment settings (image, env vars)
    - Workspace and config mounts from the request
    - Extra mounts from the environment spec
    - Plugin-specific mounts from the agent plan

    Args:
        request: User intent for an agent run.
        agent_plan: AgentSystemPlan from the plugin.

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

    # Add plugin-specific mounts (convert from agent_systems.models.MountSpec to planner.models.MountSpec)
    # Note: Plugins handle their own config mounts to align with established container_config_dir() convention
    for plugin_mount in agent_plan.mounts:
        mounts.append(
            MountSpec(
                src=plugin_mount.src,
                dst=plugin_mount.dst,
                mode=plugin_mount.mode,  # type: ignore
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
