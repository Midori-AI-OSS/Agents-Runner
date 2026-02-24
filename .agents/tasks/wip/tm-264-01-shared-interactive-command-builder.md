# Task: Add shared interactive command builder

## Context
Issue #264 reports interactive runs using stale agent flags when an override agent is selected. The non-interactive path is correct because it always plans from the resolved agent.

## Goal
Introduce a shared helper (in `agents_runner/agent_cli.py`) that builds the interactive command using the resolved agent, mirroring the non-interactive planning logic.

## Steps
1. Inspect `build_noninteractive_cmd` and the current interactive command build path to identify the shared inputs needed.
2. Add a helper API in `agents_runner/agent_cli.py` (for example `build_interactive_cmd` or a unified helper) that accepts the resolved agent and returns the command head/args for interactive runs.
3. Ensure the helper derives flags/head from the resolved agent, not from UI-selected command head values.
4. Keep diffs minimal; avoid adding new logging or docs unless required.

## Acceptance
- Interactive and non-interactive command planning share the same agent resolution logic.
- The helper is ready for the UI interactive flow to call without independently selecting a command head.

## Checks
- Manual repro from issue #264: set base agent to Codex, override to Claude in the UI, run Interactive, and confirm the command uses Claude-specific flags/head.
