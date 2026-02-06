# Implement Copilot agent system plugin

**Parent Task:** 026-agent-system-plugins.md

## Scope
Create plugin for GitHub Copilot agent system.

## Actions
1. Create `agents_runner/agent_systems/copilot/` package
2. Create `agents_runner/agent_systems/copilot/plugin.py`:
   - Implement `CopilotPlugin` class extending `AgentSystemPlugin`
   - Set `name = "copilot"`
   - Define capabilities (non-interactive only per parent task)
   - Implement `plan(req: AgentSystemRequest) -> AgentSystemPlan`:
     - Build exec argv for copilot CLI (refer to current implementation for exact command structure)
     - Define required config mounts (e.g., `~/.copilot` to container path)
     - Set prompt delivery mode
     - Enforce policy: interactive runs not supported
3. Add UI theme spec
4. No Qt imports
5. Run linters

**Note:** Review existing Copilot execution code to determine current command structure, config mount paths, and prompt delivery mechanism before implementing.

## Acceptance
- Plugin implements contract correctly
- Interactive support correctly set to False
- Behavior matches current Copilot agent behavior
- Passes linting
- One focused commit: `[FEAT] Add Copilot agent system plugin`

## Completion
Completed successfully. Created CopilotPlugin extending AgentSystemPlugin with:
- Non-interactive only support (supports_interactive=False)
- Command structure: gh copilot --add-dir <workspace> <extra-args> -i <prompt>
- Config mount: ~/.copilot (rw)
- Prompt delivery via -i flag
- UI theme spec set to "copilot"
- Raises ValueError for interactive requests
- Passes ruff format/check
- Commit: 8ff4eee [FEAT] Add Copilot agent system plugin
