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


def _safe_agent_token(value: str) -> str:
    raw = str(value or "").strip().lower()
    safe = "".join(ch for ch in raw if ch.isalnum() or ch in {"-", "_"})
    return safe


def container_config_dir(agent: str) -> str:
    from agents_runner.agent_systems import get_agent_system
    from agents_runner.agent_systems import get_default_agent_system_name

    raw = str(agent or "").strip().lower()
    if not raw:
        raw = get_default_agent_system_name()

    try:
        return str(get_agent_system(raw).container_config_dir())
    except KeyError:
        safe = _safe_agent_token(raw)
        if safe:
            return f"{CONTAINER_HOME}/.{safe}"
        return f"{CONTAINER_HOME}/.midoriai"


def default_host_config_dir(agent: str, *, codex_default: str | None = None) -> str:
    raw = str(agent or "").strip().lower()
    if not raw:
        from agents_runner.agent_systems import get_default_agent_system_name

        raw = get_default_agent_system_name()

    if raw == "codex":
        fallback = (
            str(codex_default or "").strip()
            or os.environ.get("CODEX_HOST_CODEX_DIR", "").strip()
            or "~/.codex"
        )
        return os.path.expanduser(fallback)
    from agents_runner.agent_systems import get_agent_system

    try:
        return os.path.expanduser(get_agent_system(raw).default_host_config_dir())
    except KeyError:
        safe = _safe_agent_token(raw)
        if safe:
            return os.path.expanduser(f"~/.midoriai/.{safe}_config")
        return os.path.expanduser("~/.midoriai/.agent_config")


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


_INTERACTIVE_PROMPT_SENTINEL = "__AGENTS_RUNNER_PROMPT__"


def _strip_prompt_from_plan(
    cmd_parts: list[str], prompt_delivery: object, prompt_token: str
) -> list[str]:
    parts = list(cmd_parts)
    prompt_token = str(prompt_token or "")
    if not prompt_token:
        return parts
    mode = str(getattr(prompt_delivery, "mode", "") or "").strip().lower()
    flag = str(getattr(prompt_delivery, "flag", "") or "").strip()
    if mode == "flag":
        if flag:
            for idx in range(len(parts) - 1):
                if parts[idx] == flag and parts[idx + 1] == prompt_token:
                    parts.pop(idx + 1)
                    parts.pop(idx)
                    break
        if prompt_token in parts:
            parts.remove(prompt_token)
        return parts
    if mode == "stdin":
        if prompt_token in parts:
            parts.remove(prompt_token)
        return parts
    for idx in range(len(parts) - 1, -1, -1):
        if parts[idx] == prompt_token:
            parts.pop(idx)
            break
    return parts


def build_interactive_cmd(
    *,
    agent: str,
    prompt: str,
    host_workdir: str,
    host_config_dir: str | None = None,
    container_workdir: str = CONTAINER_WORKDIR,
    agent_cli_args: list[str] | None = None,
    command: str | None = None,
    is_help_launch: bool = False,
    help_repos_dir: str = "/home/midori-ai/.agent-help/repos",
) -> list[str]:
    agent_raw = str(agent or "").strip().lower()
    agent = normalize_agent(agent_raw)
    extra_args = list(agent_cli_args or [])
    prompt = str(prompt or "")
    command = str(command or "").strip()

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
        has_c_flag = "-c" in extra_args
        if prompt and agent_raw not in ("true", "false") and not has_c_flag:
            args.append(prompt)
        return args

    if command and not command.startswith("-"):
        cmd_parts = shlex.split(command)
        if cmd_parts:
            head = str(cmd_parts[0] or "").strip().lower()
            known = set(available_agents())
            if head not in known:
                return cmd_parts
            if normalize_agent(head) == agent:
                from agents_runner.agent_systems import get_agent_system

                return get_agent_system(agent).build_interactive_command_parts(
                    cmd_parts=cmd_parts,
                    agent_cli_args=extra_args,
                    prompt=prompt,
                    is_help_launch=is_help_launch,
                    help_repos_dir=str(help_repos_dir or ""),
                )

    from agents_runner.agent_systems import get_agent_system
    from agents_runner.agent_systems.models import (
        AgentSystemContext,
        AgentSystemRequest,
    )

    config_dir = str(host_config_dir or "").strip() or default_host_config_dir(agent)
    system = get_agent_system(agent)
    context = AgentSystemContext(
        workspace_host=Path(os.path.expanduser(host_workdir or ".")),
        workspace_container=Path(str(container_workdir)),
        config_host=Path(os.path.expanduser(config_dir)),
        config_container=system.container_config_dir(),
        extra_cli_args=[],
    )
    plan = system.plan(
        AgentSystemRequest(
            system_name=agent,
            interactive=True,
            prompt=_INTERACTIVE_PROMPT_SENTINEL,
            context=context,
        )
    )
    cmd_parts = _strip_prompt_from_plan(
        list(plan.exec_spec.argv), plan.prompt_delivery, _INTERACTIVE_PROMPT_SENTINEL
    )
    return system.build_interactive_command_parts(
        cmd_parts=cmd_parts,
        agent_cli_args=extra_args,
        prompt=prompt,
        is_help_launch=is_help_launch,
        help_repos_dir=str(help_repos_dir or ""),
    )
