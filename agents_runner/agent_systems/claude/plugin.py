"""Claude agent system plugin implementation."""

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


class ClaudePlugin(AgentSystemPlugin):
    """Plugin for Claude agent system.

    Claude is Anthropic's AI assistant with advanced reasoning capabilities.
    """

    name: str = "claude"
    capabilities: CapabilitySpec = CapabilitySpec(
        supports_noninteractive=True,
        supports_interactive=True,
        supports_cross_agents=False,
        supports_sub_agents=False,
    )
    ui_theme: UiThemeSpec | None = UiThemeSpec(theme_name="claude")
    install_command: str = 'echo "Claude CLI installation required"'

    def plan(self, req: AgentSystemRequest) -> AgentSystemPlan:
        """Generate an execution plan for Claude agent.

        Args:
            req: The agent system request containing prompt and context.

        Returns:
            An execution plan specifying how to run the Claude agent.
        """
        # Build argv for claude CLI
        argv = ["claude"]

        # Ensure workspace directory is added
        argv.extend(["--add-dir", str(req.context.workspace_container)])

        # Add any extra CLI args from context
        argv.extend(req.context.extra_cli_args)

        # Append prompt as positional argument
        argv.append(req.prompt)

        # Define config mount: ~/.claude from host to container
        claude_config_host = Path.home() / ".claude"
        claude_config_container = req.context.config_container / ".claude"

        mounts = [
            MountSpec(
                src=claude_config_host,
                dst=claude_config_container,
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
plugin = ClaudePlugin()
