# Implement Codex agent system plugin

**Parent Task:** 026-agent-system-plugins.md

## Scope
Create plugin for Codex agent system.

## Actions
1. Create `agents_runner/agent_systems/codex/` package
2. Create `agents_runner/agent_systems/codex/plugin.py`:
   - Implement `CodexPlugin` class extending `AgentSystemPlugin`
   - Set `name = "codex"`
   - Define capabilities (supports both interactive and non-interactive)
   - Implement `plan(req: AgentSystemRequest) -> AgentSystemPlan`:
     - Build exec argv for codex CLI (refer to current implementation for exact command structure)
     - Define required config mounts (e.g., `~/.codex` to container path)
     - Set prompt delivery mode
     - Handle interactive vs non-interactive
3. Add UI theme spec (references existing theme)
4. No Qt imports
5. Run linters

**Note:** Review existing Codex execution code to determine current command structure, config mount paths, and prompt delivery mechanism before implementing.

## Acceptance
- Plugin implements contract correctly
- Behavior matches current Codex agent behavior
- Passes linting
- One focused commit: `[FEAT] Add Codex agent system plugin`
