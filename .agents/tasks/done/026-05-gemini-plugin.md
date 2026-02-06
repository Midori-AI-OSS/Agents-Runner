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

## Completion Note
Completed successfully:
- Created `agents_runner/agent_systems/gemini/` package with `__init__.py` and `plugin.py`
- Implemented `GeminiPlugin` extending `AgentSystemPlugin`
- Set capabilities (supports interactive and non-interactive)
- Configured UI theme spec (gemini)
- Built exec argv matching current gemini CLI usage: `gemini --include-directories <workspace> --approval-mode yolo --no-sandbox -i <prompt>`
- Defined config mount: `~/.gemini` to container path
- Set prompt delivery mode: flag (`-i`)
- No Qt imports (follows plugin contract)
- Passed ruff format and check
- Committed with `[FEAT] Add Gemini agent system plugin` (73aab7c)
