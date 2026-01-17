## Prompt

Runtime: GitHub Copilot CLI.

This section is appended because Copilot CLI is selected and available for this run. Use it as selection guidance and execution notes (it is not identity text).

**Strengths**
- Copilot is especially well-suited as a sub-agent router/orchestrator for large-scope, long-running work. When Copilot operates in this mode, the main agent must pass the router flow/template inline in the prompt, and Copilot must follow it. Since a sub-agent router template may not exist in the target repository, Copilot must not rely on repo-local templates.
- Often more cost-effective for big tasks than many small requests (usage/cost is per request)

**Avoid when**
- The task is tiny and one-off (often less cost-effective)

**How Agents Runner runs it**
- Command:
  ```
  copilot --allow-all-tools --allow-all-paths --add-dir <WORKDIR> [extra_args] -p <PROMPT>
  ```
- Access: all tools + all paths allowed; `<WORKDIR>` is included (default `~/workspace`)
- Timeout: if the main agent is invoking Copilot for long tasks (especially as Router/Orchestrator), the main agent must bypass automatic command timeouts by setting a very high timeout (8+ hours). Some runtimes (including Codex) apply an automatic timeout to command runs.

**Prompt contract**
- When Copilot acts as Router/Orchestrator: the main agent must include the full router flow/template inline in the prompt; Copilot must restate the flow Copilot will run and then follow it strictly.
