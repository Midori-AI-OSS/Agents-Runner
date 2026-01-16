## Prompt

Runtime: GitHub Copilot CLI.

This section is appended because Copilot CLI is selected and available for this run. Use it as selection guidance and execution notes (it is not identity text).

**Strengths**
- Best for large-scope, long-running work (can run a full sub-agent flow to completion; see the Subagents Template above)
- Often more cost-effective for big tasks than many small requests (usage/cost tends to be per request in this setup)

**Avoid when**
- The task is tiny and one-off (often less cost-effective)

**How Agents Runner runs it**
- Command:
  ```
  copilot --allow-all-tools --allow-all-paths --add-dir <WORKDIR> [extra_args] -p <PROMPT>
  ```
- Access: all tools + all paths allowed; `<WORKDIR>` is included (default `~/workspace`)

**Prompt contract**
- When acting as Router/Orchestrator, state the full flow you will run, then follow the Subagents Template strictly
