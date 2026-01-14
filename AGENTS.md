# Agents Runner Contributor Guide

This project uses the Codex contributor coordination system. Follow these guidelines when contributing code, documentation, or reviewing work.

---

## Quick Start

- **Run locally:** `uv run main.py`
- **UI styling:** Located in `agents_runner/style/` (Qt stylesheet builder) and `agents_runner/widgets/` (custom widgets)
- **Preflight Review:** Read `.github/copilot-instructions.md` before starting work to understand environment, tooling, and compliance expectations.
- **Design constraint:** Keep sharp/square corners (avoid non-`0px` `border-radius` values and `addRoundedRect(...)`)
- **Code style:** Python 3.13+, type hints, minimal diffs (avoid drive-by refactors)
- **Docs:** Do not update `README.md`; prefer code and docstrings as the source of truth and keep notes minimal and task-scoped
- **Commits:** Commit early and often — prefer many small, focused commits with clear `[TYPE]` messages and concise descriptions.
- **Test:** Do not build tests unless asked to; delegate testing to Tester Mode when requested

---

## PixelArch Info
- **PixelArch Tooling:** `yay`, `gh`, and `git` are always installed in PixelArch—avoid adding auto-install or alternate toolchain paths for them
- **PixelArch Packages:** Do not use `pacman` unless the user uses it in preflight; install/update via `yay -Syu`

---

## Config & Data Directories

- `~/.midoriai`: App data folder for this program (and other Midori AI programs)
- `~/.codex`: Codex agent config folder (read-only)
- `~/.copilot`: Copilot config folder (read-only)
- `~/.claude`: Claude agent config folder (read-only)
- `~/.gemini`: Gemini CLI config folder (read-only)

---

## Development Basics

- Run `uv run main.py` to test the GUI locally before committing changes.
- Follow existing code style: Python 3.13+, type hints throughout, and minimal modifications.
- Verification-first: confirm current behavior in the codebase before changing code; reproduce/confirm the issue (or missing behavior); verify the fix with clear checks.
- No broad fallbacks: do not add “fallback behavior everywhere”; only add a narrow fallback when the task explicitly requires it, and justify it.
- No backward compatibility shims by default: do not preserve old code paths “just in case”; only add compatibility layers when the task explicitly requires it.
- Minimal documentation, minimal logging: prefer reading code and docstrings; do not add docs/logs unless required to diagnose a specific issue or prevent a crash.
- Do not update `README.md`.
- Avoid monolith files: **soft max 300 lines per file**, **hard max 600 lines per file** (split modules/classes when approaching the soft limit).
- Keep UI elements sharp—no rounded corners in stylesheets or custom painting code.
- Run linters and tests before submitting PRs.
- Use structured commit messages: `[TYPE] Concise summary`
- Break large changes into reviewable commits.

---

## Contributor Modes

Use these mode guides from `.agents/modes/` when working on specific tasks:

- **Coder Mode** (`.agents/modes/CODER.md`): Implementing features and fixes
- **Tester Mode** (`.agents/modes/TESTER.md`): Building and managing tests
- **Reviewer Mode** (`.agents/modes/REVIEWER.md`): Auditing documentation
- **Task Master Mode** (`.agents/modes/TASKMASTER.md`): Managing work items
- **Manager Mode** (`.agents/modes/MANAGER.md`): Planning and coordination
- **Auditor Mode** (`.agents/modes/AUDITOR.md`): Code and security audits
- **QA Mode** (`.agents/modes/QA.md`): Ensuring correctness and reliability

---

## Communication

Use GitHub issues/PRs/comments as the primary async communication channel. Keep commit messages and PR descriptions concise and outcome-focused.
Do not use emoticons, emoji, or other non-text icons in commit messages, issue/PR descriptions, comments, documentation, or source code.
