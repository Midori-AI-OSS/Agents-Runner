# Midori AI Base Template

This prompt provides the shared Midori AI project conventions and cleanup rules that apply to all agent CLIs.

## Prompt

Prefer the codebase and docstrings as the source of truth. Keep notes minimal and task-scoped, and avoid creating long-lived documentation artifacts unless explicitly requested.
Verification-first: confirm current behavior before changing anything; reproduce/confirm the issue (or missing behavior); verify the fix with clear checks.

When all agents are done, please remove all files in the `.agents/audit` or `.codex/audit` folder other than the `AGENTS.md`.
Never commit docs / text files other than the `AGENTS.md` / `README.md` to the repo root, delete docs or text files in root if the sub agents made them.
