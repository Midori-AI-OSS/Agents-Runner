from __future__ import annotations

import os
import re
import subprocess

from pathlib import Path

from agents_runner.agent_systems.interactive_command import move_flag_value_to_end
from agents_runner.agent_systems.interactive_command import move_positional_to_end
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
from agents_runner.agent_systems.status import StatusType
from agents_runner.agent_systems.status import command_in_path
from agents_runner.agent_systems.status import installed_status
from agents_runner.agent_systems.status import not_installed_status


CONTAINER_HOME = Path("/home/midori-ai")
WORKSPACE_DIR = "/home/midori-ai/workspace"
_OPENCODE_CONFIG_DIR = CONTAINER_HOME / ".config" / "opencode"
_OPENCODE_DATA_DIR = CONTAINER_HOME / ".local" / "share" / "opencode"
_HOST_DATA_DIR = Path("~/.local/share/opencode").expanduser()
_TOP_LEVEL_SUBCOMMANDS = {
    "completion",
    "acp",
    "mcp",
    "attach",
    "run",
    "debug",
    "providers",
    "agent",
    "upgrade",
    "uninstall",
    "serve",
    "web",
    "models",
    "stats",
    "export",
    "import",
    "github",
    "pr",
    "session",
    "db",
}
_TOP_LEVEL_VALUE_OPTIONS = {
    "--log-level",
    "--port",
    "--hostname",
    "--mdns-domain",
    "--cors",
    "-m",
    "--model",
    "-s",
    "--session",
    "--prompt",
    "--agent",
}


def _top_level_subcommand(parts: list[str]) -> str:
    if len(parts) < 2:
        return ""
    candidate = str(parts[1] or "").strip().lower()
    if candidate in _TOP_LEVEL_SUBCOMMANDS:
        return candidate
    return ""


def _has_top_level_project(parts: list[str]) -> bool:
    expect_value = False
    for token in parts[1:]:
        current = str(token or "").strip()
        if not current:
            continue
        if expect_value:
            expect_value = False
            continue
        if current in _TOP_LEVEL_VALUE_OPTIONS:
            expect_value = True
            continue
        if current.startswith("-"):
            continue
        if current.lower() in _TOP_LEVEL_SUBCOMMANDS:
            return False
        return True
    return False


def _without_variant_option(parts: list[str]) -> list[str]:
    sanitized: list[str] = []
    skip_next = False
    for part in parts:
        current = str(part or "")
        if skip_next:
            skip_next = False
            continue
        if current == "--variant":
            skip_next = True
            continue
        if current.startswith("--variant="):
            continue
        sanitized.append(part)
    return sanitized


class OpenCodeAgentSystemPlugin:
    name = "opencode"
    display_name = "OpenCode"
    capabilities = CapabilitySpec(
        supports_noninteractive=True,
        supports_interactive=True,
        supports_cross_agents=False,
        supports_sub_agents=False,
        requires_github_token=False,
    )
    ui_theme = UiThemeSpec(theme_name="opencode")

    def plan(self, req: AgentSystemRequest) -> AgentSystemPlan:
        context = req.context
        prompt = str(req.prompt or "").strip()

        argv = [
            "opencode",
            "run",
            "--dir",
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
        return _OPENCODE_CONFIG_DIR

    def default_host_config_dir(self) -> str:
        return os.path.expanduser("~/.config/opencode")

    def additional_config_mounts(self, *, host_config_dir: Path) -> list[MountSpec]:
        try:
            _HOST_DATA_DIR.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass

        return [
            MountSpec(
                src=_HOST_DATA_DIR,
                dst=_OPENCODE_DATA_DIR,
                mode="rw",
            )
        ]

    def setup_command(self) -> str | None:
        return "opencode providers login; read -p 'Press Enter to close...'"

    def config_command(self) -> str | None:
        return (
            "opencode providers list; opencode debug paths; opencode debug config; "
            "read -p 'Press Enter to close...'"
        )

    def verify_command(self) -> list[str]:
        return ["opencode", "--version"]

    def install_command(self) -> str:
        return "yay -S --noconfirm --needed opencode"

    def detect_status(self) -> AgentStatus:
        if not command_in_path("opencode"):
            return not_installed_status(agent=self.name)

        auth_file = Path.home() / ".local" / "share" / "opencode" / "auth.json"
        try:
            result = subprocess.run(
                ["opencode", "providers", "list"],
                capture_output=True,
                text=True,
                timeout=5,
            )
        except subprocess.TimeoutExpired:
            return installed_status(
                agent=self.name,
                logged_in=False,
                status_text="Unknown (timeout)",
                status_type=StatusType.UNKNOWN,
            )
        except (FileNotFoundError, OSError):
            return installed_status(
                agent=self.name,
                logged_in=False,
                status_text="Unknown (command failed)",
                status_type=StatusType.UNKNOWN,
            )

        combined = "\n".join(
            part.strip() for part in (result.stdout, result.stderr) if str(part).strip()
        )
        normalized = combined.lower()
        has_credentials = bool(
            re.search(r"\b[1-9]\d*\s+credentials?\b", normalized)
            or re.search(r"\b[1-9]\d*\s+environment variables?\b", normalized)
        )

        if result.returncode == 0 and has_credentials:
            return installed_status(
                agent=self.name,
                logged_in=True,
                status_text="Configured providers detected",
            )
        if result.returncode == 0 and auth_file.is_file():
            return installed_status(
                agent=self.name,
                logged_in=True,
                status_text="Configured credentials detected",
            )
        if result.returncode == 0:
            return installed_status(
                agent=self.name,
                logged_in=False,
                status_text="Not logged in",
            )
        return installed_status(
            agent=self.name,
            logged_in=False,
            status_text="Unknown (provider output unavailable)",
            status_type=StatusType.UNKNOWN,
        )

    def default_interactive_command(self) -> str:
        return "opencode"

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
        del is_help_launch
        del help_repos_dir

        parts = list(cmd_parts)
        subcommand = _top_level_subcommand(parts)

        if agent_cli_args:
            parts.extend(agent_cli_args)

        if subcommand and subcommand != "run":
            return _without_variant_option(parts)

        if subcommand == "run":
            if "--dir" not in parts:
                parts.extend(["--dir", WORKSPACE_DIR])
            if prompt:
                move_positional_to_end(parts, prompt)
            return parts

        parts = _without_variant_option(parts)

        if prompt:
            if "--prompt" in parts:
                move_flag_value_to_end(parts, {"--prompt"})
            else:
                parts.extend(["--prompt", prompt])

        if not _has_top_level_project(parts):
            parts.append(WORKSPACE_DIR)

        return parts


PLUGIN = OpenCodeAgentSystemPlugin()
