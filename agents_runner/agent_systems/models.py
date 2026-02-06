"""Pydantic models for agent system plugins."""

from __future__ import annotations

from abc import abstractmethod
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class PromptDeliverySpec(BaseModel):
    """Specification for how an agent CLI accepts the initial prompt."""

    mode: Literal["positional", "flag", "stdin"] = "positional"
    flag: str | None = None  # ex: "-p" (when mode="flag")


class CapabilitySpec(BaseModel):
    """Specification for agent system capabilities."""

    supports_noninteractive: bool = True
    supports_interactive: bool = True
    supports_cross_agents: bool = False
    cross_agents_level: int = Field(default=1, ge=1, le=5)
    supports_sub_agents: bool = False
    sub_agents_level: int = Field(default=1, ge=1, le=5)
    requires_github_token: bool = False


class UiThemeSpec(BaseModel):
    """Specification for agent UI theme."""

    theme_name: str  # fallback is "midoriai"


class MountSpec(BaseModel):
    """Specification for a filesystem mount."""

    src: Path
    dst: Path
    mode: Literal["ro", "rw"] = "rw"


class ExecSpec(BaseModel):
    """Specification for executing an agent command."""

    argv: list[str]
    cwd: Path | None = None
    env: dict[str, str] = Field(default_factory=dict)
    tty: bool = False
    stdin: bool = False


class AgentSystemContext(BaseModel):
    """Context information provided to agent system plugins."""

    workspace_host: Path
    workspace_container: Path
    config_host: Path
    config_container: Path
    extra_cli_args: list[str] = Field(default_factory=list)


class AgentSystemRequest(BaseModel):
    """Request to plan an agent system execution."""

    system_name: str
    interactive: bool = False
    prompt: str
    context: AgentSystemContext


class AgentSystemPlan(BaseModel):
    """Plan produced by an agent system plugin."""

    system_name: str
    interactive: bool
    capabilities: CapabilitySpec
    mounts: list[MountSpec] = Field(default_factory=list)
    exec_spec: ExecSpec
    prompt_delivery: PromptDeliverySpec = Field(default_factory=PromptDeliverySpec)


class AgentSystemPlugin(BaseModel):
    """Base class for agent system plugins.

    Plugins must implement the `plan` method to produce an execution plan
    from a given request.
    """

    name: str
    capabilities: CapabilitySpec = Field(default_factory=CapabilitySpec)
    ui_theme: UiThemeSpec | None = None
    install_command: str = 'echo "planned"'
    display_name: str | None = None
    github_url: str | None = None
    config_dir_name: str | None = None
    default_interactive_command: str | None = None

    @abstractmethod
    def plan(self, req: AgentSystemRequest) -> AgentSystemPlan:
        """Generate an execution plan for the given request.

        Args:
            req: The agent system request containing prompt and context.

        Returns:
            An execution plan specifying how to run the agent.
        """
        ...
