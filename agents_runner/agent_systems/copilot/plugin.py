"""GitHub Copilot agent system plugin implementation."""

from __future__ import annotations

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


class CopilotPlugin(AgentSystemPlugin):
    """Plugin for GitHub Copilot agent system.

    GitHub Copilot is an AI pair programmer from GitHub.
    Supports non-interactive mode only.
    """

    name: str = "copilot"
    capabilities: CapabilitySpec = CapabilitySpec(
        supports_noninteractive=True,
        supports_interactive=False,
        supports_cross_agents=False,
        supports_sub_agents=False,
        requires_github_token=True,
    )
    ui_theme: UiThemeSpec | None = UiThemeSpec(theme_name="copilot")
    install_command: str = 'echo "GitHub Copilot CLI installation required"'
    display_name: str | None = "GitHub Copilot"
    github_url: str | None = "https://github.com/github/copilot-cli"
    config_dir_name: str | None = ".copilot"
    default_interactive_command: str | None = "--add-dir /home/midori-ai/workspace"

    def plan(self, req: AgentSystemRequest) -> AgentSystemPlan:
        """Generate an execution plan for GitHub Copilot agent.

        Args:
            req: The agent system request containing prompt and context.

        Returns:
            An execution plan specifying how to run the GitHub Copilot agent.

        Raises:
            ValueError: If interactive mode is requested.
        """
        # Enforce non-interactive policy
        if req.interactive:
            raise ValueError(
                "GitHub Copilot agent system does not support interactive mode"
            )

        # Build argv for copilot CLI
        argv = ["gh", "copilot"]

        # Add workspace directory
        argv.extend(["--add-dir", str(req.context.workspace_container)])

        # Add any extra CLI args from context
        argv.extend(req.context.extra_cli_args)

        # Add prompt with -i flag for non-interactive mode
        argv.extend(["-i", req.prompt])

        # Define config mount using the configured host config directory
        # Host: <config_host> (respects user-selected config directory)
        # Container: /home/midori-ai/.copilot (aligns with container_config_dir("copilot"))
        copilot_config_host = req.context.config_host
        copilot_config_container = Path("/home/midori-ai") / ".copilot"

        mounts = [
            MountSpec(
                src=copilot_config_host,
                dst=copilot_config_container,
                mode="rw",
            )
        ]

        # Build exec spec (non-interactive: no tty, no stdin)
        exec_spec = ExecSpec(
            argv=argv,
            cwd=req.context.workspace_container,
            tty=False,
            stdin=False,
        )

        # Prompt is delivered via -i flag
        prompt_delivery = PromptDeliverySpec(mode="flag", flag="-i")

        return AgentSystemPlan(
            system_name=self.name,
            interactive=False,
            capabilities=self.capabilities,
            mounts=mounts,
            exec_spec=exec_spec,
            prompt_delivery=prompt_delivery,
        )


# Export the plugin instance for registry auto-discovery
plugin = CopilotPlugin()
