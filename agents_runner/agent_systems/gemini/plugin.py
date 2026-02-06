"""Gemini agent system plugin implementation."""

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


class GeminiPlugin(AgentSystemPlugin):
    """Plugin for Gemini agent system.

    Gemini is Google's AI assistant with advanced code understanding capabilities.
    """

    name: str = "gemini"
    capabilities: CapabilitySpec = CapabilitySpec(
        supports_noninteractive=True,
        supports_interactive=True,
        supports_cross_agents=False,
        supports_sub_agents=False,
    )
    ui_theme: UiThemeSpec | None = UiThemeSpec(theme_name="gemini")
    install_command: str = 'echo "Gemini CLI installation required"'
    display_name: str | None = "Google Gemini"
    github_url: str | None = "https://github.com/google-gemini/gemini-cli"
    config_dir_name: str | None = ".gemini"
    default_interactive_command: str | None = (
        "--no-sandbox --approval-mode yolo --include-directories /home/midori-ai/workspace"
    )

    def plan(self, req: AgentSystemRequest) -> AgentSystemPlan:
        """Generate an execution plan for Gemini agent.

        Args:
            req: The agent system request containing prompt and context.

        Returns:
            An execution plan specifying how to run the Gemini agent.
        """
        # Build argv for gemini CLI
        argv = ["gemini"]

        # Add workspace directory
        argv.extend(["--include-directories", str(req.context.workspace_container)])

        # Set approval mode to yolo
        argv.extend(["--approval-mode", "yolo"])

        # Set sandbox mode (no-sandbox for full access)
        argv.append("--no-sandbox")

        # Add any extra CLI args from context
        argv.extend(req.context.extra_cli_args)

        # Add prompt with -i flag for interactive prompt delivery
        argv.extend(["-i", req.prompt])

        # Define config mount: ~/.gemini from host to container
        gemini_config_host = Path.home() / ".gemini"
        gemini_config_container = req.context.config_container / ".gemini"

        mounts = [
            MountSpec(
                src=gemini_config_host,
                dst=gemini_config_container,
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

        # Prompt is delivered via -i flag
        prompt_delivery = PromptDeliverySpec(mode="flag", flag="-i")

        return AgentSystemPlan(
            system_name=self.name,
            interactive=req.interactive,
            capabilities=self.capabilities,
            mounts=mounts,
            exec_spec=exec_spec,
            prompt_delivery=prompt_delivery,
        )


# Export the plugin instance for registry auto-discovery
plugin = GeminiPlugin()
