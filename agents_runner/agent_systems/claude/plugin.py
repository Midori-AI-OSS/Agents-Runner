from __future__ import annotations

import os

from pathlib import Path

from agents_runner.agent_systems.models import (
    AgentSystemPlan,
    AgentSystemRequest,
    CapabilitySpec,
    ExecSpec,
    MountSpec,
    PromptDeliverySpec,
    UiThemeSpec,
)


CONTAINER_HOME = Path("/home/midori-ai")


class ClaudeAgentSystemPlugin:
    name = "claude"
    display_name = "Claude"
    capabilities = CapabilitySpec(
        supports_noninteractive=True,
        supports_interactive=True,
        supports_cross_agents=True,
        supports_sub_agents=True,
        requires_github_token=False,
    )
    ui_theme = UiThemeSpec(theme_name="claude")

    def plan(self, req: AgentSystemRequest) -> AgentSystemPlan:
        context = req.context
        prompt = str(req.prompt or "").strip()

        argv = [
            "claude",
            "--print",
            "--output-format",
            "text",
            "--permission-mode",
            "bypassPermissions",
            "--add-dir",
            str(context.workspace_container),
            *list(context.extra_cli_args),
            prompt,
        ]

        mounts = [
            MountSpec(
                src=context.config_host,
                dst=self.container_config_dir(),
                mode="rw",
            ),
            *self.additional_config_mounts(host_config_dir=context.config_host),
        ]

        return AgentSystemPlan(
            system_name=self.name,
            interactive=bool(req.interactive),
            capabilities=self.capabilities,
            mounts=mounts,
            exec_spec=ExecSpec(argv=argv),
            prompt_delivery=PromptDeliverySpec(mode="positional"),
        )

    def container_config_dir(self) -> Path:
        return CONTAINER_HOME / ".claude"

    def default_host_config_dir(self) -> str:
        return os.path.expanduser("~/.claude")

    def additional_config_mounts(self, *, host_config_dir: Path) -> list[MountSpec]:
        host_dir = Path(os.path.expanduser(str(host_config_dir))).resolve()
        settings_path = host_dir.parent / ".claude.json"
        if settings_path.is_file():
            return [
                MountSpec(
                    src=settings_path,
                    dst=CONTAINER_HOME / ".claude.json",
                    mode="rw",
                )
            ]
        return []

    def setup_command(self) -> str | None:
        # Launches interactive setup inside a terminal.
        return "claude; read -p 'Press Enter to close...'"

    def config_command(self) -> str | None:
        return None

    def verify_command(self) -> list[str]:
        return ["claude", "--version"]


PLUGIN = ClaudeAgentSystemPlugin()
