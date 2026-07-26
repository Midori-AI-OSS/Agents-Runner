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
from agents_runner.agent_systems.interactive_command import move_positional_to_end
from agents_runner.agent_systems.status import AgentStatus
from agents_runner.agent_systems.status import StatusType
from agents_runner.agent_systems.status import command_in_path
from agents_runner.agent_systems.status import installed_status
from agents_runner.agent_systems.status import not_installed_status


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

    def install_command(self) -> str:
        return "yay -S --noconfirm --needed claude-code"

    def detect_status(self) -> AgentStatus:
        if not command_in_path("claude"):
            return not_installed_status(agent=self.name)

        config_dir = Path.home() / ".claude"
        if not config_dir.exists():
            return installed_status(
                agent=self.name,
                logged_in=False,
                status_text="Not logged in (no config)",
            )

        try:
            if any(config_dir.iterdir()):
                return installed_status(
                    agent=self.name,
                    logged_in=True,
                    status_text="Possibly logged in (config exists)",
                    status_type=StatusType.UNKNOWN,
                )
        except OSError:
            pass

        return installed_status(
            agent=self.name,
            logged_in=False,
            status_text="Not logged in",
        )

    def default_interactive_command(self) -> str:
        return "--add-dir /home/midori-ai/workspace"

    def sanitize_interactive_command_parts(self, *, cmd_parts: list[str]) -> list[str]:
        return list(cmd_parts)

    def build_interactive_command_parts(
        self,
        *,
        cmd_parts: list[str],
        agent_cli_args: list[str],
        prompt: str,
    ) -> list[str]:
        parts = list(cmd_parts)

        if agent_cli_args:
            parts.extend(agent_cli_args)

        if "--add-dir" not in parts:
            parts[1:1] = ["--add-dir", "/home/midori-ai/workspace"]

        if prompt:
            move_positional_to_end(parts, prompt)

        return parts


PLUGIN = ClaudeAgentSystemPlugin()
