# Agents Runner Contributor Guide

This project uses the Codex contributor coordination system. Follow these guidelines when contributing code, documentation, or reviewing work.

---

## Quick Start

- **Run locally:** `uv run main.py`
- **UI styling:** Located in `agents_runner/style/` (Qt stylesheet builder) and `agents_runner/widgets/` (custom widgets)
- **Design constraint:** Keep sharp/square corners (avoid non-`0px` `border-radius` values and `addRoundedRect(...)`)
- **Code style:** Python 3.13+, type hints, minimal diffs (avoid drive-by refactors)
- **Docs:** Do not update the readme unless asked to
- **Test:** Do not build tests unless asked to; place tests under `tests/` (create it if missing)

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

---

## Development Basics

- Run `uv run main.py` to test the GUI locally before committing changes.
- Follow existing code style: Python 3.13+, type hints throughout, and minimal modifications.
- Avoid monolith files: **soft max 300 lines per file**, **hard max 600 lines per file** (split modules/classes when approaching the soft limit).
- Keep UI elements sharp—no rounded corners in stylesheets or custom painting code.
- Run linters and tests before submitting PRs.
- Use structured commit messages: `[TYPE] Concise summary`
- Break large changes into reviewable commits.

---

## Contributor Modes

Use these mode guides from `.codex/modes/` when working on specific tasks:

- **Coder Mode** (`.codex/modes/CODER.md`): Implementing features and fixes
- **Reviewer Mode** (`.codex/modes/REVIEWER.md`): Auditing documentation
- **Task Master Mode** (`.codex/modes/TASKMASTER.md`): Managing work items
- **Manager Mode** (`.codex/modes/MANAGER.md`): Planning and coordination
- **Auditor Mode** (`.codex/modes/AUDITOR.md`): Code and security audits

---

## Communication

Use GitHub issues/PRs/comments as the primary async communication channel. Keep commit messages and PR descriptions concise and outcome-focused.
