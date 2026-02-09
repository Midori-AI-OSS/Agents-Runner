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


PLUGIN = GeminiAgentSystemPlugin()
