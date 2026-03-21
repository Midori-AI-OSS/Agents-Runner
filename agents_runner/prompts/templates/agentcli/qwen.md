## Prompt

Runtime: Qwen Code CLI.

This section is appended because Qwen is selected and available for this run. Use it as selection guidance and execution notes.

**Strengths**
- Good general-purpose code work when you want a Gemini-like CLI flow without assuming Gemini-specific flags

**Avoid when**
- The task depends on undocumented Qwen CLI behavior or flags that were not confirmed from `qwen --help`

**How Agents Runner runs it**
- Command:
  ```
  qwen --approval-mode yolo --include-directories <WORKDIR> [extra_args] <PROMPT>
  ```
- Interactive prompt seeding uses `-i <PROMPT>` / `--prompt-interactive <PROMPT>`
- Access: `<WORKDIR>` is included (default `~/workspace`)
- Safety: only confirmed Qwen flags are assumed; do not assume `--no-sandbox`
- Compatibility: positional prompts are preferred for one-shot runs; `-p/--prompt` exists only as deprecated compatibility

**Config and auth**
- Default config root: `~/.qwen`
- MVP note: setup can launch normally even when login-status UI remains `Unknown`

**Prompt contract**
- Treat `<PROMPT>` as the full task input for one-shot runs
- Keep Qwen-specific guidance limited to confirmed runtime behavior
