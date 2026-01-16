## Prompt

Runtime: Claude CLI.

This section is appended because Claude CLI is selected and available for this run. Use it as selection guidance and execution notes (it is not identity text).

**Strengths**
- General-purpose all-rounder

**Avoid when**
- You need the repo maintainer to locally reproduce/validate Claude-specific behavior (they may not be able to test Claude right now)

**How Agents Runner runs it**
- Command:
  ```
  claude --print --output-format text --permission-mode bypassPermissions --add-dir <WORKDIR> [extra_args] <PROMPT>
  ```
- Access: `<WORKDIR>` is included (default `~/workspace`)

**Prompt contract**
- Treat `<PROMPT>` as the full task input (non-interactive); return results directly and keep meta commentary minimal
