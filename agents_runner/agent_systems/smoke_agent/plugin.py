from __future__ import annotations

import os
import shlex

from pathlib import Path

from agents_runner.agent_systems.models import (
    AgentSystemPlan,
    AgentSystemRequest,
    CapabilitySpec,
    ExecSpec,
    MountSpec,
    PromptDeliverySpec,
)


CONTAINER_HOME = Path("/home/midori-ai")


class SmokeAgentSystemPlugin:
    name = "smoke_agent"
    display_name = "Smoke Agent"
    internal_only = True
    capabilities = CapabilitySpec(
        supports_noninteractive=True,
        supports_interactive=False,
        supports_cross_agents=False,
        supports_sub_agents=False,
        requires_github_token=False,
    )
    ui_theme = None

    def plan(self, req: AgentSystemRequest) -> AgentSystemPlan:
        context = req.context
        prompt = str(req.prompt or "").strip()
        extra_args = [
            str(arg).strip()
            for arg in (context.extra_cli_args or [])
            if str(arg).strip()
        ]

        if extra_args:
            argv = ["sh", *extra_args]
            has_c_flag = "-c" in extra_args or "-lc" in extra_args
            if prompt and not has_c_flag:
                argv.extend(["-lc", f"printf '%s\\n' {shlex.quote(prompt)}"])
        else:
            script = "true"
            if prompt:
                script = f"printf '%s\\n' {shlex.quote(prompt)}"
            argv = ["sh", "-lc", script]

        mounts = [
            MountSpec(
                src=context.config_host,
                dst=self.container_config_dir(),
                mode="rw",
            ),
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
        return CONTAINER_HOME / ".smoke_agent"

    def default_host_config_dir(self) -> str:
        return os.path.expanduser("~/.midoriai/.smoke_agent_config")

    def additional_config_mounts(self, *, host_config_dir: Path) -> list[MountSpec]:
        return []

    def setup_command(self) -> str | None:
        return None

    def config_command(self) -> str | None:
        return None

    def verify_command(self) -> list[str]:
        return ["sh", "-lc", "echo smoke_agent ready"]

    def default_interactive_command(self) -> str:
        return ""

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
        return [*list(cmd_parts), *list(agent_cli_args)]


PLUGIN = SmokeAgentSystemPlugin()
