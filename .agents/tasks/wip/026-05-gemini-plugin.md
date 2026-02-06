# Implement Gemini agent system plugin

**Parent Task:** 026-agent-system-plugins.md

## Scope
Create plugin for Google Gemini agent system.

## Actions
1. Create `agents_runner/agent_systems/gemini/` package
2. Create `agents_runner/agent_systems/gemini/plugin.py`:
   - Implement `GeminiPlugin` class extending `AgentSystemPlugin`
   - Set `name = "gemini"`
   - Define capabilities
   - Implement `plan(req: AgentSystemRequest) -> AgentSystemPlan`:
     - Build exec argv for gemini CLI (refer to current implementation for exact command structure)
     - Define required config mounts (e.g., `~/.gemini` to container path)
     - Set prompt delivery mode
     - Handle interactive vs non-interactive
3. Add UI theme spec
4. No Qt imports
5. Run linters

**Note:** Review existing Gemini execution code to determine current command structure, config mount paths, and prompt delivery mechanism before implementing.

## Acceptance
- Plugin implements contract correctly
- Behavior matches current Gemini agent behavior
- Passes linting
- One focused commit: `[FEAT] Add Gemini agent system plugin`
