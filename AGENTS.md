# Agents Runner Contributor Guide

This project uses the Codex contributor coordination system. Follow these guidelines when contributing code, documentation, or reviewing work.

---

## Quick Start

- **Run locally:** `uv run main.py`
- **UI styling:** Located in `codex_local_conatinerd/style.py` (Qt stylesheet) and `codex_local_conatinerd/widgets.py` (custom widgets)
- **Design constraint:** Keep sharp/square corners (avoid `border-radius` and `addRoundedRect(...)`)
- **Code style:** Python 3.13+, type hints, minimal diffs (avoid drive-by refactors)
- **Docs:** Do not update the readme unless asked to
- **Test:** Do not build tests unless asked to, tests go in the test folder

---

## PixelArch Info
- **PixelArch tooling:** `yay`, `gh`, and `git` are always installed in PixelArch—do not add fallbacks for missing binaries
- **PixelArch Packages:** Do not use `pacman` unless the user uses it in preflight; install/update via `yay -Syu`

---

## Development Basics

- Run `uv run main.py` to test the GUI locally before committing changes.
- Follow existing code style: Python 3.13+, type hints throughout, and minimal modifications.
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

Other modes available: Blogger, Brainstormer, Prompter, Storyteller

---

## Communication

Open issues or PRs on GitHub for significant changes. Keep commit messages and PR descriptions concise and outcome-focused.
