## Prompt

Runtime: Gemini CLI.

This section is appended because Gemini CLI is selected and available for this run. Use it as selection guidance and execution notes (it is not identity text).

**Strengths**
- Good for small tasks and reviews (good tooling; easy prompting)
- Often usable on free tiers, with okay rate limits for small work

**Avoid when**
- The task is mid/large scope (rate limits can block finishing)

**How Agents Runner runs it**
- Command:
  ```
  gemini --no-sandbox --approval-mode yolo --include-directories <WORKDIR> --include-directories /tmp [extra_args] <PROMPT>
  ```
- Access: `<WORKDIR>` is included (default `~/workspace`) and `/tmp` is included
- Security: `--no-sandbox` + `--approval-mode yolo` (tool calls are auto-approved); be careful with destructive actions
- Prompt is appended positionally (no `--prompt` or `-p`)

**Prompt contract**
- Keep scope tight; avoid long-running orchestration in this runtime
