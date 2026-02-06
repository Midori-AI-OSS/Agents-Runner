# Agent system plugins (folder-based)

Issue
- Agent CLIs are hardcoded in multiple places (command building, config mounts, token forwarding, prompt templates, UI theme background), making it hard to add/remove agent systems cleanly.

Goal
- Introduce a Python plugin system for “agent systems” where each agent has its own folder/module and a standardized Pydantic contract.
- Make it easy to add/remove an agent system by adding/removing one folder + registering it.
- Centralize agent capabilities/policy (supports interactive, prompt policy, mounts/env, setup/verify commands) behind the plugin contract.
- Move UI background/theme selection behind the same plugin name so removing a plugin removes its UI background too (UI code stays under `agents_runner/ui/`).

Related issues
- #161 Agent Systems Plugins
- #54 Implement Qwen-Code Agent

Completion
- When completing this task, reference the related issue(s) above in commit messages and in the PR body.

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

---

## Completion Note

**Date:** 2025-02-06
**Status:** ✅ Complete

### Summary
All subtasks completed successfully:

1. ✅ **Models and Registry**: `agents_runner/agent_systems/models.py` and `registry.py` implemented with Pydantic contract and auto-discovery
2. ✅ **Agent Plugins**: All 4 built-in plugins implemented (codex, claude, copilot, gemini) under `agents_runner/agent_systems/<name>/plugin.py`
3. ✅ **UI Theme Integration**: UI background system queries plugin `ui_theme.theme_name` via `_theme_for_agent()` in `graphics.py`
4. ✅ **Planner Integration**: `planner.py` calls `plugin.plan()` to generate execution plans instead of hardcoded branching
5. ✅ **Cleanup**: Core agent system branching logic migrated to plugin capabilities queries

### Plugin System Features
- Auto-discovery from `agents_runner/agent_systems/*/plugin.py`
- Safe loading with error handling (import failures logged, don't crash app)
- Pydantic models for type safety and validation
- Capability-based checks (interactive support, GitHub token requirements, etc.)
- Plugin-specific mounts and exec configuration
- UI theme integration via plugin metadata

### Verification
- ✅ All plugins load and register correctly
- ✅ Planner generates correct execution plans for all agent systems
- ✅ `uv run --group lint ruff check .` passes
- ✅ `uv run --group lint ruff format .` passes
- ✅ Manual testing confirms behavior matches pre-plugin implementation

### Out of Scope (Correctly Preserved)
- UI command routing in `main_window_tasks_interactive_command.py` (UI-specific logic)
- Settings key mapping in `main_window_settings.py` (configuration layer)
- Legacy Docker config fields (backward compatibility)
- Display names and URLs in `agent_display.py` (metadata, not plugin logic)

### Related Issues
- Addresses #161 Agent Systems Plugins
- Enables #54 Implement Qwen-Code Agent (plugin infrastructure ready)
