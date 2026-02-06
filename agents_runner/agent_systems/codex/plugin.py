"""Codex agent system plugin implementation."""

from __future__ import annotations

import subprocess
from pathlib import Path

from agents_runner.agent_systems.models import (
    AgentSystemPlan,
    AgentSystemPlugin,
    AgentSystemRequest,
    CapabilitySpec,
    ExecSpec,
    MountSpec,
    PromptDeliverySpec,
    UiThemeSpec,
)


def _is_git_repo_root(path: Path) -> bool:
    """Check if the given path is a git repository root.

    Args:
        path: The path to check.

    Returns:
        True if the path is a git repository root, False otherwise.
    """
    if not path.is_dir():
        return False
    try:
        proc = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "--is-inside-work-tree"],
            check=False,
            capture_output=True,
            text=True,
            timeout=2.0,
            stdin=subprocess.DEVNULL,
        )
    except Exception:
        return False
    return proc.returncode == 0 and (proc.stdout or "").strip().lower() == "true"


class CodexPlugin(AgentSystemPlugin):
    """Plugin for Codex agent system.

    Codex is OpenAI's code-understanding agent system.
    """

    name: str = "codex"
    capabilities: CapabilitySpec = CapabilitySpec(
        supports_noninteractive=True,
        supports_interactive=True,
        supports_cross_agents=False,
        supports_sub_agents=False,
    )
    ui_theme: UiThemeSpec | None = UiThemeSpec(theme_name="codex")
    install_command: str = 'echo "Codex CLI installation required"'
    display_name: str | None = "OpenAI Codex"
    github_url: str | None = "https://github.com/openai/codex"
    config_dir_name: str | None = ".codex"
    default_interactive_command: str | None = "--sandbox danger-full-access"

    def plan(self, req: AgentSystemRequest) -> AgentSystemPlan:
        """Generate an execution plan for Codex agent.

        Args:
            req: The agent system request containing prompt and context.

        Returns:
            An execution plan specifying how to run the Codex agent.
        """
        # Build argv for codex CLI
        argv = [
            "codex",
            "exec",
            "--sandbox",
            "danger-full-access",
        ]

        # Skip git repo check if workspace is not a git repo
        if not _is_git_repo_root(req.context.workspace_host):
            argv.append("--skip-git-repo-check")

        # Add any extra CLI args from context
        argv.extend(req.context.extra_cli_args)

        # Append prompt as positional argument
        argv.append(req.prompt)

        # Define config mount using the configured host config directory
        # Host: <config_host> (respects user-selected config directory)
        # Container: /home/midori-ai/.codex (aligns with container_config_dir("codex"))
        codex_config_host = req.context.config_host
        codex_config_container = Path("/home/midori-ai") / ".codex"

        mounts = [
            MountSpec(
                src=codex_config_host,
                dst=codex_config_container,
                mode="rw",
            )
        ]

        # Build exec spec
        exec_spec = ExecSpec(
            argv=argv,
            cwd=req.context.workspace_container,
            tty=req.interactive,
            stdin=req.interactive,
        )

        # Prompt is delivered as a positional argument
        prompt_delivery = PromptDeliverySpec(mode="positional")

        return AgentSystemPlan(
            system_name=self.name,
            interactive=req.interactive,
            capabilities=self.capabilities,
            mounts=mounts,
            exec_spec=exec_spec,
            prompt_delivery=prompt_delivery,
        )


# Export the plugin instance for registry auto-discovery
plugin = CodexPlugin()
