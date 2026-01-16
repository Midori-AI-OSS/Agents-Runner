# Task — Create subagentstemplate.md

## 1. Title (short)
Create shared sub-agent orchestration template

## 2. Summary (1–3 sentences)
Create `agents_runner/prompts/templates/subagentstemplate.md` with shared sub-agent prompting instructions. Extract and adapt the sub-agent routing logic from the existing `template.md` (lines 9-97).

## 3. Implementation notes (key decisions + constraints)
- Create file: `agents_runner/prompts/templates/subagentstemplate.md`
- Source content from `agents_runner/prompts/template.md` (lines 9-105, the entire sub-agent orchestration logic):
  - Lines 9-13: System detection instructions (check `~/.codex`, `~/.claude`, `~/.gemini`, `~/.copilot`)
  - Lines 15-96: Main Agent orchestration rules when sub-agents are supported
    - Control directory determination (`<CONTROL_DIR>`)
    - Task workflow (Task Master → Auditor → Coder → Auditor → Task Master)
    - Trivial tasks shortcut
    - Core loop and routing rules
    - Cleanup instructions
  - Lines 98-105: Direct execution mode when sub-agents not supported
- Include `## Prompt` marker at the top
- This content is intentionally generic and CLI-agnostic
- Should be ~95-100 lines (the bulk of the orchestration logic)

## 4. Acceptance criteria (clear, testable statements)
- File `agents_runner/prompts/templates/subagentstemplate.md` exists
- File contains `## Prompt` marker
- File can be loaded via `load_prompt("templates/subagentstemplate")` without errors
- Content includes both "sub agents supported" and "sub agents not supported" branches
- Content includes system detection logic, task folder structure, and routing rules

## 5. Expected files to modify (explicit paths)
- Add: `agents_runner/prompts/templates/subagentstemplate.md`

## 6. Out of scope (what not to do)
- Do not include Midori AI base context (goes in midoriaibasetemplate.md)
- Do not include cross-agent instructions (goes in crossagentstemplate.md)
- Do not include CLI-specific commands (goes in agentcli/*.md)
- Do not modify template.md yet (will be deprecated in later task)
- Do not modify any Python code
- Do not update `README.md` or add tests

---

## Completion Note
Task completed successfully.
- Created `agents_runner/prompts/templates/subagentstemplate.md` with 98 lines
- Extracted sub-agent orchestration logic from `template.md` (lines 9-105)
- Includes system detection, task workflow, routing rules, and both supported/unsupported branches
- Verified file loads successfully via `load_prompt("templates/subagentstemplate")`
- All acceptance criteria met
