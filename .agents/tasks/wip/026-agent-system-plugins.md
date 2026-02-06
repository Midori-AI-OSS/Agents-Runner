# Agent system plugins (folder-based)

Issue
- Agent CLIs are hardcoded in multiple places (command building, config mounts, token forwarding, prompt templates, UI theme background), making it hard to add/remove agent systems cleanly.

Goal
- Introduce a Python plugin system for “agent systems” where each agent has its own folder/module and a standardized Pydantic contract.
- Make it easy to add/remove an agent system by adding/removing one folder + registering it.
- Centralize agent capabilities/policy (supports interactive, prompt policy, mounts/env, setup/verify commands) behind the plugin contract.
- Move UI background/theme selection behind the same plugin name so removing a plugin removes its UI background too (UI code stays under `agents_runner/ui/`).

Notes
- Plugins do not own Docker image selection or caching. Image + caching stays environment-driven (PixelArch + existing preflight/desktop caching).
- Env vars + extra mounts are environment-driven (`EnvironmentSpec` in task 025).

Scope (tie-in)
- Integrate with the unified flow work in `025-unify-runplan-pydantic.md` so the planner/runner calls the agent-system plugin instead of branching on strings.

Folder layout (proposed)
- `agents_runner/agent_systems/`
  - `__init__.py`
  - `registry.py` (discover/register plugins, select by name)
  - `models.py` (Pydantic types below)
  - `<system_name>/`
    - `__init__.py`
    - `plugin.py` (implements the contract; no Qt imports)
- `agents_runner/ui/themes/<system_name>/` (plugin-owned UI background implementation)

Plugin loading (safety)
- Auto-load built-in plugins from `agents_runner/agent_systems/*/plugin.py`.
- Safety checks: unique `name`, valid `capabilities`, import failures do not crash the app (skip + log).

Model prototype (Pydantic sketch)
```py
from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class PromptDeliverySpec(BaseModel):
    # how the agent CLI accepts the initial prompt
    mode: Literal["positional", "flag", "stdin"] = "positional"
    flag: str | None = None  # ex: "-p" (when mode="flag")


class CapabilitySpec(BaseModel):
    supports_noninteractive: bool = True
    supports_interactive: bool = True
    supports_cross_agents: bool = False
    cross_agents_level: int = Field(default=1, ge=1, le=5)
    supports_sub_agents: bool = False
    sub_agents_level: int = Field(default=1, ge=1, le=5)


class UiThemeSpec(BaseModel):
    theme_name: str  # fallback is "midoriai"


class MountSpec(BaseModel):
    src: Path
    dst: Path
    mode: Literal["ro", "rw"] = "rw"


class ExecSpec(BaseModel):
    argv: list[str]
    cwd: Path | None = None
    env: dict[str, str] = Field(default_factory=dict)
    tty: bool = False
    stdin: bool = False


class AgentSystemContext(BaseModel):
    workspace_host: Path
    workspace_container: Path
    config_host: Path
    config_container: Path
    extra_cli_args: list[str] = Field(default_factory=list)


class AgentSystemRequest(BaseModel):
    system_name: str
    interactive: bool = False
    prompt: str
    context: AgentSystemContext


class AgentSystemPlan(BaseModel):
    system_name: str
    interactive: bool
    capabilities: CapabilitySpec
    mounts: list[MountSpec] = Field(default_factory=list)
    exec_spec: ExecSpec
    prompt_delivery: PromptDeliverySpec = Field(default_factory=PromptDeliverySpec)


class AgentSystemPlugin(BaseModel):
    name: str
    capabilities: CapabilitySpec = Field(default_factory=CapabilitySpec)
    ui_theme: UiThemeSpec | None = None
    install_command: str = 'echo "planned"'

    def plan(self, req: AgentSystemRequest) -> AgentSystemPlan: ...
```

Subtasks (small, reviewable)
- Add `agents_runner/agent_systems/models.py` + `registry.py`.
- Implement plugins for current built-ins (codex/claude/copilot/gemini) under `agents_runner/agent_systems/<name>/plugin.py`.
- Teach the UI background system to select theme/background by plugin `name` (no hardcoded per-agent mapping).
- Migrate existing codepaths to query plugin outputs (exec argv/env, mounts, prompt policy, interactive support).
- Deprecate/remove scattered string-branch logic once callers are migrated.

Constraints
- No Qt imports outside `agents_runner/ui/`.
- Minimal diffs per subtask; avoid drive-by refactors.

Verify
- `uv run --group lint ruff check .`
- `uv run --group lint ruff format .`
- Manual: run each supported agent system (non-interactive) and confirm behavior matches current.
