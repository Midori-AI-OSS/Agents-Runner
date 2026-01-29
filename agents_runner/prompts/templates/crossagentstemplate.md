# Cross-Agent Template

This prompt enables cross-agent coordination by providing information about available agent CLIs in the environment.

## Prompt

Cross-agents are enabled for this environment.

This section is appended because cross-agent CLIs are available for this run. Use it as coordination guidance (it is not identity text).

When coordinating work across different agent systems:
- Select the appropriate CLI runtime based on the task and the environment configuration
- If this prompt includes a runtime-specific guidance section (for example: Codex/Copilot/Gemini/Claude), follow it
- Coordinate asynchronously: invoke the CLI, capture output, and proceed based on results
- Keep tool usage scoped; do not run multiple agent CLIs concurrently unless the task explicitly requires it

Cross-agent orchestration allows leveraging specialized capabilities from different LRM systems within a single workflow.
