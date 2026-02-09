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


class GeminiAgentSystemPlugin:
    name = "gemini"
    display_name = "Gemini"
    capabilities = CapabilitySpec(
        supports_noninteractive=True,
        supports_interactive=True,
        supports_cross_agents=True,
        supports_sub_agents=True,
        requires_github_token=False,
    )
    ui_theme = UiThemeSpec(theme_name="gemini")

    def plan(self, req: AgentSystemRequest) -> AgentSystemPlan:
        context = req.context
        prompt = str(req.prompt or "").strip()

        argv = [
            "gemini",
            "--no-sandbox",
            "--approval-mode",
            "yolo",
            "--include-directories",
            str(context.workspace_container),
            "--include-directories",
            "/tmp",
            *list(context.extra_cli_args),
        ]
        if prompt:
            argv.append(prompt)

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
        return CONTAINER_HOME / ".gemini"

    def default_host_config_dir(self) -> str:
        return os.path.expanduser("~/.gemini")

    def additional_config_mounts(self, *, host_config_dir: Path) -> list[MountSpec]:
        return []

    def setup_command(self) -> str | None:
        return None

    def config_command(self) -> str | None:
        return None

    def verify_command(self) -> list[str]:
        return ["gemini", "--version"]

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

        if "--include-directories" not in parts:
            parts[1:1] = ["--include-directories", "/home/midori-ai/workspace"]

        if is_help_launch:
            if help_repos_dir not in parts:
                parts[1:1] = ["--include-directories", help_repos_dir]

            if "--sandbox" in parts:
                idx = parts.index("--sandbox")
                parts.pop(idx)
                if idx < len(parts) and not parts[idx].startswith("-"):
                    parts.pop(idx)
            if "-s" in parts:
                parts.remove("-s")

            if "--no-sandbox" not in parts:
                parts[1:1] = ["--no-sandbox"]

        if (
            "--sandbox" not in parts
            and "--no-sandbox" not in parts
            and "-s" not in parts
        ):
            parts[1:1] = ["--no-sandbox"]

        if "--approval-mode" not in parts:
            parts[1:1] = ["--approval-mode", "yolo"]

        if prompt:
            has_interactive_prompt = "-i" in parts or "--prompt-interactive" in parts
            has_prompt = "-p" in parts or "--prompt" in parts
            if has_interactive_prompt:
                move_flag_value_to_end(parts, {"-i", "--prompt-interactive"})
            elif has_prompt:
                move_flag_value_to_end(parts, {"-p", "--prompt"})
            else:
                parts.extend(["-i", prompt])

        return parts


PLUGIN = GeminiAgentSystemPlugin()
