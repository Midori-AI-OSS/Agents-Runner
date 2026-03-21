## Prompt

Runtime: OpenCode CLI.

This section is appended because OpenCode is selected and available for this run. Use it as selection guidance and execution notes.

**Strengths**
- Best when you want OpenCode itself, especially for TUI or WebUI-driven sessions

**Avoid when**
- You need polished one-shot CLI automation; `opencode run` works, but it is rougher than OpenCode's preferred TUI/WebUI flows

**How Agents Runner runs it**
- Non-interactive command:
  ```
  opencode run --dir <WORKDIR> [extra_args] <PROMPT>
  ```
- Interactive command:
  ```
  opencode [options] [--prompt <PROMPT>] <WORKDIR>
  ```
- Persistence: both `~/.config/opencode` and `~/.local/share/opencode` are mounted so config, auth, and session data stay available

**Setup and status**
- Login flow: `opencode providers login`
- Status/debug: `opencode providers list`, `opencode debug paths`

**Prompt contract**
- Prefer OpenCode TUI/WebUI for longer sessions
- Use `opencode run` as the app's CLI fallback, not as proof that the CLI is OpenCode's best mode
