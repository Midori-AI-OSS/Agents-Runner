# Cross-Agent Template

This prompt enables cross-agent coordination by providing information about available agent CLIs in the environment.

## Prompt

Cross-agents are enabled for this environment. Multiple agent CLI tools are mounted and available for invocation.

When coordinating work across different agent systems:
- Check environment configuration for available cross-agent CLIs
- Use the appropriate CLI tool based on the task requirements
- Each agent CLI has its own interface and capabilities (see agentcli/*.md for details)
- Coordinate asynchronously: invoke the CLI, capture output, and proceed based on results

Cross-agent orchestration allows leveraging specialized capabilities from different AI systems within a single workflow.
