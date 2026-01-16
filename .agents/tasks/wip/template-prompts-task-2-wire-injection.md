# Task — Wire template injection to templates + per-agent-CLI prompts

## 1. Title (short)
Replace `load_prompt("template")` with `templates/*` + `templates/agentcli/*`

## 2. Summary (1–3 sentences)
Update the non-interactive worker prompt assembly so that when the Midori AI template is detected, it injects the new prompt files from `agents_runner/prompts/templates/` instead of `agents_runner/prompts/template.md`. Do not embed prompt strings in Python; load the shared template prompt plus a per-agent-CLI prompt markdown file.

## 3. Implementation notes (key decisions + constraints)
- Current injection point: `agents_runner/docker/agent_worker.py:376`–`400`.
- Keep the existing detection condition: only inject when `template_detection.midoriai_template_detected` is true.
- Injection behavior should become:
  - Always append `load_prompt("templates/allprompttemplate")`.
  - Always append the per-CLI prompt: `load_prompt(f"templates/agentcli/{agent_cli}")` (where `agent_cli` is already normalized in the worker).
- Do not add the “sub agents not supported” branch here; we’ll do per-CLI prompting later by filling in the placeholder markdown files (the code should already be wired to load them).
- Important: do not “hard code” prompt strings in Python. All template instructions must be stored in `.md` files and loaded via `load_prompt(...)`.
- Keep logging behavior roughly equivalent; it’s ok to adjust the log message text to reflect the new prompts (e.g. “injected template prompts”).
- Decide what to do with `agents_runner/prompts/template.md`:
  - Either delete it (if no longer referenced), or replace it with a short deprecation note that points to the new `templates/` prompts.
  - If you keep it, make sure it’s not used by runtime code anymore (only the `templates/*` prompts should be injected).

## 4. Acceptance criteria (clear, testable statements)
- `agents_runner/docker/agent_worker.py` no longer calls `load_prompt("template")`.
- When template is detected, the injected content includes `templates/allprompttemplate` plus `templates/agentcli/<agent_cli>`.
- When template is not detected, no template prompts are injected (unchanged behavior).

## 5. Expected files to modify (explicit paths)
- `agents_runner/docker/agent_worker.py`
- Potentially: `agents_runner/prompts/template.md` (delete or deprecate)

## 6. Out of scope (what not to do)
- No UI changes.
- Do not update `README.md` or add tests.

## Notes — Non-interactive agent CLI entrypoints (repo-grounded)
Source of truth for how this app starts each agent non-interactively: `agents_runner/agent_cli.py` (`build_noninteractive_cmd`).

Quick reference (current behavior):
- `codex`: `codex exec --sandbox danger-full-access [--skip-git-repo-check] <PROMPT>`
- `claude`: `claude --print --output-format text --permission-mode bypassPermissions --add-dir <WORKDIR> <PROMPT>`
- `copilot`: `copilot --allow-all-tools --allow-all-paths --add-dir <WORKDIR> -p <PROMPT>`
- `gemini`: `gemini --no-sandbox --approval-mode yolo --include-directories <WORKDIR> --include-directories /tmp [<PROMPT>]`
  - Agents Runner appends the prompt positionally only when non-empty (no `--prompt` flag is used).
- Docker validation PixelArch image: `lunamidori5/pixelarch:emerald` (`agents_runner/ui/dialogs/docker_validator.py`, `agents_runner/ui/constants.py`).

Use these command-shape notes as part of the placeholder content for each per-CLI template file in `agents_runner/prompts/templates/agentcli/` (i.e. include the relevant “how this CLI is invoked by Agents Runner” snippet inside `codex.md`, `claude.md`, `copilot.md`, and `gemini.md`).
