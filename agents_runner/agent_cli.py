import os
import shlex

from pathlib import Path


CONTAINER_HOME = "/home/midori-ai"
CONTAINER_WORKDIR = "/home/midori-ai/workspace"


def normalize_agent(value: str | None) -> str:
    from agents_runner.agent_systems import normalize_agent_system_name

    return normalize_agent_system_name(value)


def available_agents() -> list[str]:
    from agents_runner.agent_systems import available_agent_system_names

    return available_agent_system_names()


def container_config_dir(agent: str) -> str:
    agent = normalize_agent(agent)
    from agents_runner.agent_systems import get_agent_system

    try:
        return str(get_agent_system(agent).container_config_dir())
    except KeyError:
        return f"{CONTAINER_HOME}/.codex"


def default_host_config_dir(agent: str, *, codex_default: str | None = None) -> str:
    agent = normalize_agent(agent)
    if agent == "codex":
        fallback = (
            str(codex_default or "").strip()
            or os.environ.get("CODEX_HOST_CODEX_DIR", "").strip()
            or "~/.codex"
        )
        return os.path.expanduser(fallback)
    from agents_runner.agent_systems import get_agent_system

    try:
        return os.path.expanduser(get_agent_system(agent).default_host_config_dir())
    except KeyError:
        return os.path.expanduser("~/.codex")


def agent_requires_github_token(agent: str) -> bool:
    agent = normalize_agent(agent)
    from agents_runner.agent_systems import get_agent_system

    try:
        plugin = get_agent_system(agent)
    except KeyError:
        return False
    return bool(getattr(plugin.capabilities, "requires_github_token", False))


def additional_config_mounts(agent: str, host_config_dir: str) -> list[str]:
    agent = normalize_agent(agent)
    host = str(host_config_dir or "").strip()
    if not host:
        return []

    from agents_runner.agent_systems import get_agent_system

    try:
        plugin = get_agent_system(agent)
    except KeyError:
        return []

    mounts = plugin.additional_config_mounts(
        host_config_dir=Path(os.path.expanduser(host))
    )
    rendered: list[str] = []
    for mount in mounts:
        docker_mount = mount.to_docker_mount()
        if docker_mount.endswith(":rw"):
            docker_mount = docker_mount[:-3]
        rendered.append(docker_mount)
    return rendered


def verify_cli_clause(agent: str) -> str:
    agent_raw = str(agent or "").strip().lower()
    # For test commands, verify the raw command name
    # Handle both relative (sh, bash) and absolute paths (/bin/sh, /bin/bash)
    if agent_raw in (
        "echo",
        "sh",
        "bash",
        "true",
        "false",
        "/bin/sh",
        "/bin/bash",
        "/usr/bin/sh",
        "/usr/bin/bash",
    ):
        agent = agent_raw
    else:
        agent = normalize_agent(agent_raw)
    quoted = shlex.quote(agent)
    return (
        f"command -v {quoted} >/dev/null 2>&1 || "
        "{ "
        f'echo "{agent} not found in PATH=$PATH"; '
        "exit 127; "
        "}; "
    )


def build_noninteractive_cmd(
    *,
    agent: str,
    prompt: str,
    host_workdir: str,
    host_config_dir: str | None = None,
    container_workdir: str = CONTAINER_WORKDIR,
    agent_cli_args: list[str] | None = None,
) -> list[str]:
    agent_raw = str(agent or "").strip().lower()
    agent = normalize_agent(agent_raw)
    extra_args = list(agent_cli_args or [])
    prompt = str(prompt or "").strip()

    # Support test/debug commands as pass-through (for testing only)
    # Handle both relative (sh, bash) and absolute paths (/bin/sh, /bin/bash)
    if agent_raw in (
        "echo",
        "sh",
        "bash",
        "true",
        "false",
        "/bin/sh",
        "/bin/bash",
        "/usr/bin/sh",
        "/usr/bin/bash",
    ):
        args = [agent_raw, *extra_args]
        # For sh/bash with -c, the command is already in extra_args, don't append prompt
        # For echo/true/false without -c, conditionally append prompt
        has_c_flag = "-c" in extra_args
        if prompt and agent_raw not in ("true", "false") and not has_c_flag:
            args.append(prompt)
        return args

    from agents_runner.agent_systems import get_agent_system
    from agents_runner.agent_systems.models import (
        AgentSystemContext,
        AgentSystemRequest,
    )

    config_dir = str(host_config_dir or "").strip() or default_host_config_dir(agent)
    context = AgentSystemContext(
        workspace_host=Path(os.path.expanduser(host_workdir or ".")),
        workspace_container=Path(str(container_workdir)),
        config_host=Path(os.path.expanduser(config_dir)),
        config_container=get_agent_system(agent).container_config_dir(),
        extra_cli_args=extra_args,
    )
    plan = get_agent_system(agent).plan(
        AgentSystemRequest(
            system_name=agent,
            interactive=False,
            prompt=prompt,
            context=context,
        )
    )
    return list(plan.exec_spec.argv)
