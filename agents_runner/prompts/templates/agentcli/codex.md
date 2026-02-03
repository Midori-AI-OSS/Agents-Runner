## Prompt

Runtime: Codex CLI.

This section is appended because Codex CLI is selected and available for this run. Use it as selection guidance and execution notes.

**Strengths**
- Strong for short, high-complexity work and hard-to-debug issues
- Can use MCP tooling if configured in this environment (for example: context7, playwright)

**Avoid when**
- The work is large-scope and long-running
- Usage/limits make many small attempts expensive

**How Agents Runner runs it**
- Command:
  ```
  codex exec --sandbox danger-full-access [--skip-git-repo-check] -o /tmp/agents-artifacts/<name>.md <PROMPT> > /tmp/agents-artifacts/subagent-run.log 2>&1
  ```
- Sandbox: full-access
- Git repo check: `--skip-git-repo-check` is added when workspace type is not WORKSPACE_CLONED

**Artifacts and chatter control**
- Prefer `-o <artifact.md>` to capture the final answer in an artifacts file (for example `/tmp/agents-artifacts/<name>.md`, where `<name>` is the subagent task name).
- Redirect any extra CLI chatter into a separate log artifact (example: `> /tmp/agents-artifacts/subagent-run.log 2>&1`).

**MCP servers**
- Add/remove: edit `~/.codex/config.toml` under `mcp_servers` (add a table to enable; delete it to disable)
- Example:
  ```toml
  [mcp_servers.playwright]
  command = "npx"
  type = "stdio"
  args = ["-y", "@playwright/mcp@latest"]
  ```

**Prompt contract**
- Treat `<PROMPT>` as the full task input (non-interactive); return results directly and keep meta commentary minimal
- For large-scope / long-running work, prefer delegating to Copilot (as Router/Orchestrator) when available, rather than orchestrating across multiple agent CLIs yourself.
