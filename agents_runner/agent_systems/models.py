from __future__ import annotations

from pathlib import Path
from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field


class PromptDeliverySpec(BaseModel):
    """How an agent CLI accepts the initial prompt."""

    model_config = ConfigDict(extra="forbid")

    mode: Literal["positional", "flag", "stdin"] = "positional"
    flag: str | None = None


class CapabilitySpec(BaseModel):
    """Declares what an agent system supports.

    Levels are 1–5 to allow coarse ordering without overfitting to vendor details.
    """

    model_config = ConfigDict(extra="forbid")

    supports_noninteractive: bool = True
    supports_interactive: bool = True
    supports_cross_agents: bool = False
    cross_agents_level: int = Field(default=1, ge=1, le=5)
    supports_sub_agents: bool = False
    sub_agents_level: int = Field(default=1, ge=1, le=5)

    requires_github_token: bool = False


class UiThemeSpec(BaseModel):
    """UI theme selection for the agent system (used by `agents_runner/ui/`)."""

    model_config = ConfigDict(extra="forbid")

    theme_name: str


class MountSpec(BaseModel):
    """A host → container mount required by the agent system."""

    model_config = ConfigDict(extra="forbid")

    src: Path
    dst: Path
    mode: Literal["ro", "rw"] = "rw"

    def to_docker_mount(self) -> str:
        suffix = f":{self.mode}" if self.mode else ""
        return f"{self.src}:{self.dst}{suffix}"


class ExecSpec(BaseModel):
    """Execution plan for an agent CLI invocation."""

    model_config = ConfigDict(extra="forbid")

    argv: list[str]
    cwd: Path | None = None
    env: dict[str, str] = Field(default_factory=dict)
    tty: bool = False
    stdin: bool = False


class AgentSystemContext(BaseModel):
    """Runtime context for planning an agent system invocation."""

    model_config = ConfigDict(extra="forbid")

    workspace_host: Path
    workspace_container: Path
    config_host: Path
    config_container: Path
    extra_cli_args: list[str] = Field(default_factory=list)


class AgentSystemRequest(BaseModel):
    """Request to plan an agent system invocation."""

    model_config = ConfigDict(extra="forbid")

    system_name: str
    interactive: bool = False
    prompt: str = ""
    context: AgentSystemContext


class AgentSystemPlan(BaseModel):
    """Planned invocation for an agent system."""

    model_config = ConfigDict(extra="forbid")

    system_name: str
    interactive: bool
    capabilities: CapabilitySpec
    mounts: list[MountSpec] = Field(default_factory=list)
    exec_spec: ExecSpec
    prompt_delivery: PromptDeliverySpec = Field(default_factory=PromptDeliverySpec)


@runtime_checkable
class AgentSystemPlugin(Protocol):
    """Folder-based agent system plugin contract."""

    name: str
    display_name: str
    capabilities: CapabilitySpec
    ui_theme: UiThemeSpec | None

    def plan(self, req: AgentSystemRequest) -> AgentSystemPlan: ...

    def container_config_dir(self) -> Path: ...

    def default_host_config_dir(self) -> str: ...

    def additional_config_mounts(self, *, host_config_dir: Path) -> list[MountSpec]: ...

    def setup_command(self) -> str | None: ...

    def config_command(self) -> str | None: ...

    def verify_command(self) -> list[str]: ...

    def sanitize_interactive_command_parts(self, *, cmd_parts: list[str]) -> list[str]:
        """Normalize interactive command parts for storage in settings.

        This is used by the UI to strip agent-specific prefixes (for example:
        Codex's `exec`) after removing the leading agent executable name.
        """
        ...

    def build_interactive_command_parts(
        self,
        *,
        cmd_parts: list[str],
        agent_cli_args: list[str],
        prompt: str,
        is_help_launch: bool,
        help_repos_dir: str,
    ) -> list[str]: ...
