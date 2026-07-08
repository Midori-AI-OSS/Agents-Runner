from __future__ import annotations

import os
import subprocess

from pathlib import Path

from agents_runner.agent_systems.interactive_command import move_flag_value_to_end
from agents_runner.agent_systems.models import (
    AgentSystemPlan,
    AgentSystemRequest,
    CapabilitySpec,
    ExecSpec,
    MountSpec,
    PromptDeliverySpec,
    UiThemeSpec,
)
from agents_runner.agent_systems.status import AgentStatus
from agents_runner.agent_systems.status import command_in_path
from agents_runner.agent_systems.status import not_installed_status
from agents_runner.agent_systems.status import unknown_installed_status


CONTAINER_HOME = Path("/home/midori-ai")
WORKSPACE_DIR = "/home/midori-ai/workspace"
_QWEN_SUBCOMMANDS = {"mcp", "extensions", "hooks", "hook"}


def _ensure_include_directory(parts: list[str], directory: str) -> None:
    directory = str(directory or "").strip()
    if not directory:
        return

    for idx, part in enumerate(parts[:-1]):
        if part != "--include-directories":
            continue
        if parts[idx + 1] == directory:
            return

    parts.extend(["--include-directories", directory])


class QwenAgentSystemPlugin:
    name = "qwen"
    display_name = "Qwen"
    capabilities = CapabilitySpec(
        supports_noninteractive=True,
        supports_interactive=True,
        supports_cross_agents=False,
        supports_sub_agents=False,
        requires_github_token=False,
    )
    ui_theme = UiThemeSpec(theme_name="qwen")

    def plan(self, req: AgentSystemRequest) -> AgentSystemPlan:
        context = req.context
        prompt = str(req.prompt or "").strip()

        argv = [
            "qwen",
            "--approval-mode",
            "yolo",
            "--include-directories",
            str(context.workspace_container),
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
        return CONTAINER_HOME / ".qwen"

    def default_host_config_dir(self) -> str:
        return os.path.expanduser("~/.qwen")

    def additional_config_mounts(self, *, host_config_dir: Path) -> list[MountSpec]:
        return []

    def setup_command(self) -> str | None:
        return "qwen; read -p 'Press Enter to close...'"

    def config_command(self) -> str | None:
        return "qwen --help; read -p 'Press Enter to close...'"

    def verify_command(self) -> list[str]:
        return ["sh", "-lc", "qwen --version && qwen --help >/dev/null"]

    def install_command(self) -> str:
        return "yay -S --noconfirm --needed qwen-code"

    def detect_status(self) -> AgentStatus:
        if not command_in_path("qwen"):
            return not_installed_status(agent=self.name)

        try:
            version_result = subprocess.run(
                ["qwen", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            help_result = subprocess.run(
                ["qwen", "--help"],
                capture_output=True,
                text=True,
                timeout=5,
            )
        except subprocess.TimeoutExpired:
            return unknown_installed_status(
                agent=self.name,
                message="Unknown (qwen runtime check timed out)",
            )
        except (FileNotFoundError, OSError):
            return unknown_installed_status(
                agent=self.name,
                message="Unknown (qwen runtime check failed)",
            )

        if version_result.returncode == 0 and help_result.returncode == 0:
            return unknown_installed_status(
                agent=self.name,
                message="Installed; login status unknown",
            )
        return unknown_installed_status(
            agent=self.name,
            message="Unknown (qwen runtime check failed)",
        )

    def default_interactive_command(self) -> str:
        return "--approval-mode yolo --include-directories /home/midori-ai/workspace"

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

        subcommand = ""
        if len(parts) >= 2:
            candidate = str(parts[1] or "").strip().lower()
            if candidate in _QWEN_SUBCOMMANDS:
                subcommand = candidate

        if agent_cli_args:
            parts.extend(agent_cli_args)

        if subcommand:
            return parts

        if "--approval-mode" not in parts:
            parts[1:1] = ["--approval-mode", "yolo"]

        _ensure_include_directory(parts, WORKSPACE_DIR)

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


PLUGIN = QwenAgentSystemPlugin()
