# Task: Wire UI interactive flow to shared builder

## Context
The interactive UI path currently assembles the command head/flags inside the UI modules, which can leave stale agent flags when the override agent changes.

## Goal
Route the interactive UI through the shared helper in `agents_runner/agent_cli.py` and remove UI-specific command-head selection logic.

## Steps
1. Update `agents_runner/ui/main_window_tasks_interactive_command.py` to call the shared helper and use its output for command preview/launch.
2. Ensure `agents_runner/ui/interactive_prep_worker.py` and `agents_runner/ui/main_window_tasks_interactive.py` pass the resolved agent (override/env selection) into the helper path.
3. Remove or bypass UI logic that selects a command head independently of the resolved agent.
4. Keep diffs minimal; avoid drive-by refactors.

## Acceptance
- UI no longer chooses a command head on its own; the resolved agent is the source of truth.
- Interactive command preview/launch uses the shared helper output across overrides.

## Checks
- Manual repro from issue #264: set base agent to Codex, override to Claude or Gemini in the UI, run Interactive, and confirm the command uses the override agent flags/head.
