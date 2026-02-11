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
from agents_runner.agent_systems.interactive_command import move_flag_value_to_end


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
            *self.additional_config_mounts(host_config_dir=context.config_host),
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

    def additional_config_mounts(self, *, host_config_dir: Path) -> list[MountSpec]:
        return []

    def setup_command(self) -> str | None:
        return "gh auth login && gh copilot explain 'hello'; read -p 'Press Enter to close...'"

    def config_command(self) -> str | None:
        return "gh copilot config; read -p 'Press Enter to close...'"

    def verify_command(self) -> list[str]:
        return ["copilot", "--version"]

    def sanitize_interactive_command_parts(self, *, cmd_parts: list[str]) -> list[str]:
        return list(cmd_parts)

    def build_interactive_command_parts(
        self,
        *,
        cmd_parts: list[str],
        agent_cli_args: list[str],
        prompt: str,
        is_help_launch: bool,
        help_repos_dir: str,
    ) -> list[str]:
        parts = list(cmd_parts)

        if agent_cli_args:
            parts.extend(agent_cli_args)

        if "--add-dir" not in parts:
            parts[1:1] = ["--add-dir", "/home/midori-ai/workspace"]

        if is_help_launch:
            if "--allow-all-tools" not in parts:
                parts[1:1] = ["--allow-all-tools"]
            if "--allow-all-paths" not in parts:
                parts[1:1] = ["--allow-all-paths"]
            if help_repos_dir not in parts:
                parts[1:1] = ["--add-dir", help_repos_dir]

        if prompt:
            has_interactive = "-i" in parts or "--interactive" in parts
            has_prompt = "-p" in parts or "--prompt" in parts
            if has_prompt:
                move_flag_value_to_end(parts, {"-p", "--prompt"})
            elif not has_interactive:
                parts.extend(["-i", prompt])

        return parts


PLUGIN = CopilotAgentSystemPlugin()
