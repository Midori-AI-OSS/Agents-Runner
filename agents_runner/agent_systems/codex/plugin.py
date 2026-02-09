from __future__ import annotations

import os
import subprocess

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


CONTAINER_HOME = Path("/home/midori-ai")


def _is_git_repo_root(path: Path) -> bool:
    path = Path(os.path.expanduser(str(path))).resolve()
    if not path.is_dir():
        return False
    try:
        proc = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "--is-inside-work-tree"],
            check=False,
            capture_output=True,
            text=True,
            timeout=2.0,
            stdin=subprocess.DEVNULL,
        )
    except Exception:
        return False
    return proc.returncode == 0 and (proc.stdout or "").strip().lower() == "true"


class CodexAgentSystemPlugin:
    name = "codex"
    display_name = "Codex"
    capabilities = CapabilitySpec(
        supports_noninteractive=True,
        supports_interactive=True,
        supports_cross_agents=False,
        supports_sub_agents=False,
        requires_github_token=False,
    )
    ui_theme = UiThemeSpec(theme_name="codex")

    def plan(self, req: AgentSystemRequest) -> AgentSystemPlan:
        context = req.context
        prompt = str(req.prompt or "").strip()

        argv = ["codex", "exec", "--sandbox", "danger-full-access"]
        if not _is_git_repo_root(context.workspace_host):
            argv.append("--skip-git-repo-check")
        argv.extend(list(context.extra_cli_args))
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
        return CONTAINER_HOME / ".codex"

    def default_host_config_dir(self) -> str:
        fallback = os.environ.get("CODEX_HOST_CODEX_DIR", "").strip() or "~/.codex"
        return os.path.expanduser(fallback)

    def additional_config_mounts(self, *, host_config_dir: Path) -> list[MountSpec]:
        return []

    def setup_command(self) -> str | None:
        return "codex login; read -p 'Press Enter to close...'"

    def config_command(self) -> str | None:
        return "codex --help; read -p 'Press Enter to close...'"

    def verify_command(self) -> list[str]:
        return ["codex", "--version"]

    def sanitize_interactive_command_parts(self, *, cmd_parts: list[str]) -> list[str]:
        parts = list(cmd_parts)
        if parts and parts[0] == "exec":
            parts.pop(0)
        return parts

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

        if len(parts) >= 2 and parts[1] == "exec":
            parts.pop(1)

        if agent_cli_args:
            parts.extend(agent_cli_args)

        if is_help_launch:
            found_sandbox = False
            for idx in range(len(parts) - 1):
                if parts[idx] != "--sandbox":
                    continue
                parts[idx + 1] = "danger-full-access"
                found_sandbox = True
            if not found_sandbox:
                parts[1:1] = ["--sandbox", "danger-full-access"]

        if prompt:
            move_positional_to_end(parts, prompt)

        return parts


PLUGIN = CodexAgentSystemPlugin()
