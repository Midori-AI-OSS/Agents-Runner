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

## Completion Notes
- Created `agents_runner/agent_systems/claude/` package with `__init__.py`
- Implemented `ClaudePlugin` class extending `AgentSystemPlugin`
- Set name to "claude" with appropriate capabilities
- Implemented `plan()` method that:
  - Builds exec argv: `['claude', '--add-dir', <workspace>, ...]`
  - Defines config mount: `~/.claude` to container path
  - Sets prompt delivery mode to positional
  - Handles interactive vs non-interactive (tty/stdin)
- Added UI theme spec referencing "claude"
- No Qt imports used
- Passes ruff format and check
- Plugin successfully registered and tested
- Committed as: [FEAT] Add Claude agent system plugin
