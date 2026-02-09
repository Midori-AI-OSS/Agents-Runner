from __future__ import annotations

import os

from pathlib import Path

from agents_runner.agent_systems.models import (
    AgentSystemContext,
    AgentSystemPlan,
    AgentSystemRequest,
    CapabilitySpec,
    ExecSpec,
    MountSpec,
    PromptDeliverySpec,
    UiThemeSpec,
)


CONTAINER_HOME = Path("/home/midori-ai")


class CopilotAgentSystemPlugin:
    name = "copilot"
    display_name = "GitHub Copilot"
    capabilities = CapabilitySpec(
        supports_noninteractive=True,
        supports_interactive=True,
        supports_cross_agents=True,
        supports_sub_agents=True,
        requires_github_token=True,
    )
    ui_theme = UiThemeSpec(theme_name="copilot")

    def plan(self, req: AgentSystemRequest) -> AgentSystemPlan:
        context = req.context
        prompt = str(req.prompt or "").strip()

        argv = [
            "copilot",
            "--allow-all-tools",
            "--allow-all-paths",
            "--add-dir",
            str(context.workspace_container),
            *list(context.extra_cli_args),
            "-p",
            prompt,
        ]

        mounts = [
            MountSpec(
                src=context.config_host,
                dst=self.container_config_dir(),
                mode="rw",
            ),
            *self.additional_config_mounts(
                host_config_dir=context.config_host, context=context
            ),
        ]

        return AgentSystemPlan(
            system_name=self.name,
            interactive=bool(req.interactive),
            capabilities=self.capabilities,
            mounts=mounts,
            exec_spec=ExecSpec(argv=argv),
            prompt_delivery=PromptDeliverySpec(mode="flag", flag="-p"),
        )

    def container_config_dir(self) -> Path:
        return CONTAINER_HOME / ".copilot"

    def default_host_config_dir(self) -> str:
        return os.path.expanduser("~/.copilot")

    def additional_config_mounts(
        self, *, host_config_dir: Path, context: AgentSystemContext
    ) -> list[MountSpec]:
        return []

    def setup_command(self) -> str | None:
        return "gh auth login && gh copilot explain 'hello'; read -p 'Press Enter to close...'"

    def config_command(self) -> str | None:
        return "gh copilot config; read -p 'Press Enter to close...'"

    def verify_command(self) -> list[str]:
        return ["copilot", "--version"]


PLUGIN = CopilotAgentSystemPlugin()
