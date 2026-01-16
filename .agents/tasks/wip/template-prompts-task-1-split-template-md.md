# Task — Split `template.md` into templates + per-agent-CLI placeholders

## 1. Title (short)
Move template prompting to `templates/` + `templates/agentcli/`

## 2. Summary (1–3 sentences)
Create a new prompt subfolder and move template prompting into a shared template prompt plus per-agent-CLI placeholder prompts. Do not embed (“hard code”) any prompt strings in Python; prompts must live in markdown files.

## 3. Implementation notes (key decisions + constraints)
- Today, the template prompt is injected only in non-interactive runs when the Midori AI template is detected (`agents_runner/docker/agent_worker.py:376` loads `load_prompt("template")`).
- `load_prompt(name)` resolves to `agents_runner/prompts/{name}.md` and supports subpaths like `templates/foo` (because it uses `Path(...) / f"{name}.md"`) (`agents_runner/prompts/loader.py:45`).
- Create a new folder: `agents_runner/prompts/templates/`.
- Create a new folder: `agents_runner/prompts/templates/agentcli/`.
- Create these new prompt files (exact filenames):
  - `agents_runner/prompts/templates/allprompttemplate.md`
  - `agents_runner/prompts/templates/agentcli/codex.md`
  - `agents_runner/prompts/templates/agentcli/claude.md`
  - `agents_runner/prompts/templates/agentcli/copilot.md`
  - `agents_runner/prompts/templates/agentcli/gemini.md`
- Content guidance:
  - `allprompttemplate.md` should contain shared “template context” content (keep it minimal and stable).
  - The four `templates/agentcli/*.md` files are placeholders for future per-CLI prompting; for now they can be minimal placeholder text, but the files must exist.
- Remove the “sub agents not supported template” split from this plan (no `subagentsnotsupportedtemplate.md` file).
- Follow the existing prompt file convention by including a `## Prompt` marker and placing the actual prompt text after it (see `agents_runner/prompts/headless_desktop.md`).
- Do not add new logic here; just create the markdown prompt files.

## 4. Acceptance criteria (clear, testable statements)
- The new files exist under `agents_runner/prompts/templates/` and `agents_runner/prompts/templates/agentcli/`.
- Each new file can be loaded by `load_prompt("templates/<name-without-.md>")` and `load_prompt("templates/agentcli/<agent>")` without errors.
- No Python code embeds template prompt strings; prompts live in markdown files only.

## 5. Expected files to modify (explicit paths)
- `agents_runner/prompts/template.md` (source content for splitting; may be left as-is until Task 2)
- Add:
  - `agents_runner/prompts/templates/allprompttemplate.md`
  - `agents_runner/prompts/templates/agentcli/codex.md`
  - `agents_runner/prompts/templates/agentcli/claude.md`
  - `agents_runner/prompts/templates/agentcli/copilot.md`
  - `agents_runner/prompts/templates/agentcli/gemini.md`

## 6. Out of scope (what not to do)
- Do not change when template detection happens (`agents_runner/midoriai_template.py`).
- Do not change runtime prompt injection logic yet (handled by Task 2).
- Do not update `README.md` or add tests.
