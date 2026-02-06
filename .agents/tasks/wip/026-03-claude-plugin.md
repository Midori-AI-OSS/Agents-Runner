# Implement Claude agent system plugin

**Parent Task:** 026-agent-system-plugins.md

## Scope
Create plugin for Claude agent system.

## Actions
1. Create `agents_runner/agent_systems/claude/` package
2. Create `agents_runner/agent_systems/claude/plugin.py`:
   - Implement `ClaudePlugin` class extending `AgentSystemPlugin`
   - Set `name = "claude"`
   - Define capabilities
   - Implement `plan(req: AgentSystemRequest) -> AgentSystemPlan`:
     - Build exec argv for claude CLI (refer to current implementation for exact command structure)
     - Define required config mounts (e.g., `~/.claude` to container path)
     - Set prompt delivery mode
     - Handle interactive vs non-interactive
3. Add UI theme spec
4. No Qt imports
5. Run linters

**Note:** Review existing Claude execution code to determine current command structure, config mount paths, and prompt delivery mechanism before implementing.

## Acceptance
- Plugin implements contract correctly
- Behavior matches current Claude agent behavior
- Passes linting
- One focused commit: `[FEAT] Add Claude agent system plugin`
