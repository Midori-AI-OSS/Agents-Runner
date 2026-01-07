"""Command builder for interactive agent tasks.

This module handles the construction of agent-specific CLI commands with
proper argument handling for different agent types (codex, claude, copilot, gemini).
"""

from __future__ import annotations

import shlex


def build_agent_command_parts(
    command: str,
    agent_cli: str,
    agent_cli_args: list[str],
    prompt: str,
    is_help_launch: bool,
    help_repos_dir: str = "/home/midori-ai/.agent-help/repos",
) -> list[str]:
    """Build agent-specific command parts with proper argument handling.

    Handles agent-specific flags and argument positioning for:
    - codex: --sandbox flags, positional prompt
    - claude: --add-dir, --permission-mode
    - copilot: --allow-all-tools, --allow-all-paths
    - gemini: --include-directories, --no-sandbox, --approval-mode

    Args:
        command: Raw command string to parse
        agent_cli: Agent CLI name (codex, claude, copilot, gemini)
        agent_cli_args: Additional CLI arguments from environment config
        prompt: User prompt to inject into command
        is_help_launch: Whether this is a help mode launch
        help_repos_dir: Container path for help repos directory

    Returns:
        List of command parts ready for shell execution

    Raises:
        ValueError: If command cannot be parsed
    """
    # Parse command into parts
    if command.startswith("-"):
        cmd_parts = [agent_cli, *shlex.split(command)]
    else:
        cmd_parts = shlex.split(command)

    if not cmd_parts:
        cmd_parts = ["bash"]

    # Route to agent-specific builder
    if cmd_parts[0] == "codex":
        return _build_codex_command(
            cmd_parts, agent_cli_args, prompt, is_help_launch
        )
    elif cmd_parts[0] == "claude":
        return _build_claude_command(
            cmd_parts, agent_cli_args, prompt, is_help_launch, help_repos_dir
        )
    elif cmd_parts[0] == "copilot":
        return _build_copilot_command(
            cmd_parts, agent_cli_args, prompt, is_help_launch, help_repos_dir
        )
    elif cmd_parts[0] == "gemini":
        return _build_gemini_command(
            cmd_parts, agent_cli_args, prompt, is_help_launch, help_repos_dir
        )
    else:
        # Unknown agent, return as-is
        return cmd_parts


def _move_positional_to_end(parts: list[str], value: str) -> None:
    """Move a positional argument to the end of the command parts.

    Args:
        parts: Command parts list (modified in place)
        value: Positional argument value to move
    """
    value = str(value or "")
    if not value:
        return

    # Find and remove the positional argument (not preceded by a flag)
    for idx in range(len(parts) - 1, 0, -1):
        if parts[idx] != value:
            continue
        prev = parts[idx - 1]
        if prev != "--" and prev.startswith("-"):
            continue
        parts.pop(idx)
        break

    # Append to end
    parts.append(value)


def _move_flag_value_to_end(parts: list[str], flags: set[str]) -> None:
    """Move a flag and its value to the end of the command parts.

    Args:
        parts: Command parts list (modified in place)
        flags: Set of flag names to search for
    """
    for idx in range(len(parts) - 2, -1, -1):
        if parts[idx] in flags:
            flag = parts.pop(idx)
            value = parts.pop(idx)
            parts.extend([flag, value])
            return


def _build_codex_command(
    cmd_parts: list[str],
    agent_cli_args: list[str],
    prompt: str,
    is_help_launch: bool,
) -> list[str]:
    """Build codex-specific command with sandbox and prompt handling.

    Args:
        cmd_parts: Parsed command parts
        agent_cli_args: Additional CLI arguments
        prompt: User prompt
        is_help_launch: Whether this is help mode

    Returns:
        Modified command parts
    """
    # Remove 'exec' subcommand if present
    if len(cmd_parts) >= 2 and cmd_parts[1] == "exec":
        cmd_parts.pop(1)

    # Add agent CLI args
    if agent_cli_args:
        cmd_parts.extend(agent_cli_args)

    # Configure sandbox for help mode
    if is_help_launch:
        found_sandbox = False
        for idx in range(len(cmd_parts) - 1):
            if cmd_parts[idx] != "--sandbox":
                continue
            cmd_parts[idx + 1] = "danger-full-access"
            found_sandbox = True
        if not found_sandbox:
            cmd_parts[1:1] = ["--sandbox", "danger-full-access"]

    # Add prompt as positional argument at end
    if prompt:
        _move_positional_to_end(cmd_parts, prompt)

    return cmd_parts


def _build_claude_command(
    cmd_parts: list[str],
    agent_cli_args: list[str],
    prompt: str,
    is_help_launch: bool,
    help_repos_dir: str,
) -> list[str]:
    """Build claude-specific command with directory and permission handling.

    Args:
        cmd_parts: Parsed command parts
        agent_cli_args: Additional CLI arguments
        prompt: User prompt
        is_help_launch: Whether this is help mode
        help_repos_dir: Container path for help repos

    Returns:
        Modified command parts
    """
    # Add agent CLI args
    if agent_cli_args:
        cmd_parts.extend(agent_cli_args)

    # Ensure workspace directory is added
    if "--add-dir" not in cmd_parts:
        cmd_parts[1:1] = ["--add-dir", "/home/midori-ai/workspace"]

    # Configure for help mode
    if is_help_launch:
        if "--permission-mode" not in cmd_parts:
            cmd_parts[1:1] = ["--permission-mode", "bypassPermissions"]
        if help_repos_dir not in cmd_parts:
            cmd_parts[1:1] = ["--add-dir", help_repos_dir]

    # Add prompt as positional argument at end
    if prompt:
        _move_positional_to_end(cmd_parts, prompt)

    return cmd_parts


def _build_copilot_command(
    cmd_parts: list[str],
    agent_cli_args: list[str],
    prompt: str,
    is_help_launch: bool,
    help_repos_dir: str,
) -> list[str]:
    """Build copilot-specific command with tool and path permissions.

    Args:
        cmd_parts: Parsed command parts
        agent_cli_args: Additional CLI arguments
        prompt: User prompt
        is_help_launch: Whether this is help mode
        help_repos_dir: Container path for help repos

    Returns:
        Modified command parts
    """
    # Add agent CLI args
    if agent_cli_args:
        cmd_parts.extend(agent_cli_args)

    # Ensure workspace directory is added
    if "--add-dir" not in cmd_parts:
        cmd_parts[1:1] = ["--add-dir", "/home/midori-ai/workspace"]

    # Configure for help mode
    if is_help_launch:
        if "--allow-all-tools" not in cmd_parts:
            cmd_parts[1:1] = ["--allow-all-tools"]
        if "--allow-all-paths" not in cmd_parts:
            cmd_parts[1:1] = ["--allow-all-paths"]
        if help_repos_dir not in cmd_parts:
            cmd_parts[1:1] = ["--add-dir", help_repos_dir]

    # Add prompt with appropriate flag
    if prompt:
        has_interactive = "-i" in cmd_parts or "--interactive" in cmd_parts
        has_prompt = "-p" in cmd_parts or "--prompt" in cmd_parts
        if has_prompt:
            _move_flag_value_to_end(cmd_parts, {"-p", "--prompt"})
        elif not has_interactive:
            cmd_parts.extend(["-i", prompt])

    return cmd_parts


def _build_gemini_command(
    cmd_parts: list[str],
    agent_cli_args: list[str],
    prompt: str,
    is_help_launch: bool,
    help_repos_dir: str,
) -> list[str]:
    """Build gemini-specific command with directory and sandbox handling.

    Args:
        cmd_parts: Parsed command parts
        agent_cli_args: Additional CLI arguments
        prompt: User prompt
        is_help_launch: Whether this is help mode
        help_repos_dir: Container path for help repos

    Returns:
        Modified command parts
    """
    # Add agent CLI args
    if agent_cli_args:
        cmd_parts.extend(agent_cli_args)

    # Ensure workspace directory is included
    if "--include-directories" not in cmd_parts:
        cmd_parts[1:1] = ["--include-directories", "/home/midori-ai/workspace"]

    # Configure for help mode
    if is_help_launch:
        if help_repos_dir not in cmd_parts:
            cmd_parts[1:1] = ["--include-directories", help_repos_dir]

        # Remove sandbox flags
        if "--sandbox" in cmd_parts:
            idx = cmd_parts.index("--sandbox")
            cmd_parts.pop(idx)
            if idx < len(cmd_parts) and not cmd_parts[idx].startswith("-"):
                cmd_parts.pop(idx)
        if "-s" in cmd_parts:
            cmd_parts.remove("-s")

        # Add no-sandbox flag
        if "--no-sandbox" not in cmd_parts:
            cmd_parts[1:1] = ["--no-sandbox"]

    # Ensure sandbox mode is set
    if (
        "--sandbox" not in cmd_parts
        and "--no-sandbox" not in cmd_parts
        and "-s" not in cmd_parts
    ):
        cmd_parts[1:1] = ["--no-sandbox"]

    # Set approval mode to yolo
    if "--approval-mode" not in cmd_parts:
        cmd_parts[1:1] = ["--approval-mode", "yolo"]

    # Add prompt with appropriate flag
    if prompt:
        has_interactive_prompt = (
            "-i" in cmd_parts or "--prompt-interactive" in cmd_parts
        )
        has_prompt = "-p" in cmd_parts or "--prompt" in cmd_parts
        if has_interactive_prompt:
            _move_flag_value_to_end(cmd_parts, {"-i", "--prompt-interactive"})
        elif has_prompt:
            _move_flag_value_to_end(cmd_parts, {"-p", "--prompt"})
        else:
            cmd_parts.extend(["-i", prompt])

    return cmd_parts
