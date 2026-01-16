# Task — Wire template injection to templates + per-agent-CLI prompts

## 1. Title (short)
Replace `load_prompt("template")` with `templates/*` + `templates/agentcli/*`

## 2. Summary (1–3 sentences)
Update the non-interactive worker prompt assembly so that when the Midori AI template is detected, it injects the new prompt files from `agents_runner/prompts/templates/` instead of `agents_runner/prompts/template.md`. Do not embed prompt strings in Python; load the shared template prompt plus a per-agent-CLI prompt markdown file.

## 3. Implementation notes (key decisions + constraints)
- Current injection point: `agents_runner/docker/agent_worker.py:376`–`400`.
- Keep the existing detection condition: only inject when `template_detection.midoriai_template_detected` is true.
- Do not inject (or even attempt to `load_prompt(...)` from `templates/`) when the template is not detected.
- Do not add template-prompt injection to other execution paths (e.g. interactive runs in `agents_runner/ui/main_window_tasks_interactive.py`); this task is non-interactive worker only.
- Injection behavior should become:
  - Always append `load_prompt("templates/midoriaibasetemplate")`.
  - Always append `load_prompt("templates/subagentstemplate")`.
  - Always append the per-CLI prompt: `load_prompt(f"templates/agentcli/{agent_cli}")` (where `agent_cli` is already normalized in the worker).
- If cross-agents are enabled for the environment, append `load_prompt("templates/crossagentstemplate")` last.
- Prompt order matters; keep the concatenation order exactly as listed above.
- Cross-agents trigger (repo-grounded): mounts are enabled when `env.use_cross_agents` is true and `env.cross_agent_allowlist` is non-empty (see `agents_runner/ui/main_window_settings.py:_compute_cross_agent_config_mounts`). Use the same condition for whether to append `templates/crossagentstemplate`.
- Cross-agents state lookup: the worker only has `environment_id`; load the environment (if present) to read `use_cross_agents` and `cross_agent_allowlist`. If there is no environment (or it can’t be loaded), treat cross-agents as disabled for prompting.
- Do not add the “sub agents not supported” branch here; we’ll do per-CLI prompting later by filling in the placeholder markdown files (the code should already be wired to load them).
- Important: do not “hard code” prompt strings in Python. All template instructions must be stored in `.md` files and loaded via `load_prompt(...)`.
- Keep logging behavior roughly equivalent; it’s ok to adjust the log message text to reflect the new prompts (e.g. “injected template prompts”).
- Decide what to do with `agents_runner/prompts/template.md`:
  - Either delete it (if no longer referenced), or replace it with a short deprecation note that points to the new `templates/` prompts.
  - If you keep it, make sure it’s not used by runtime code anymore (only the `templates/*` prompts should be injected).

## 4. Acceptance criteria (clear, testable statements)
- `agents_runner/docker/agent_worker.py` no longer calls `load_prompt("template")`.
- When template is detected, the injected content includes `templates/midoriaibasetemplate`, `templates/subagentstemplate`, and `templates/agentcli/<agent_cli>` in that order.
- When template is detected and cross-agents are enabled for the environment, the injected content additionally includes `templates/crossagentstemplate` (appended last).
- When template is not detected, no template prompts are injected (unchanged behavior).
- No other code path injects or loads `templates/*` prompts (non-interactive worker only).

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

---

## Auditor Review (2025-01-16)

**Status:** ❌ FAILED REVIEW - Moved back to WIP

**Reason:** No work has been started on this task. The code at `agents_runner/docker/agent_worker.py:378` still uses the old `load_prompt("template")` call. No new template injection logic has been implemented. This task is blocked until template-prompts-task-1 is 100% complete (all markdown files from tmpl-002 through tmpl-008 must exist).

**Required Work:**
- Wait for template-prompts-task-1 to be fully completed
- Then implement new injection logic via tmpl-009
- Then deprecate old template.md via tmpl-010

**Audit Report:** /tmp/agents-artifacts/e24367e0-audit-done-tasks.audit.md
