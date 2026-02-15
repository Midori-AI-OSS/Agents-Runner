# Agents Runner Contributor Guide

This project uses the Codex contributor coordination system. Follow these guidelines when contributing code, documentation, or reviewing work.

---

## Quick Start

- **Run locally:** `uv run main.py`
- **UI:** Located in `agents_runner/ui/` (pages, widgets, styling, themes)
- **Preflight Review:** Read `.github/copilot-instructions.md` before starting work to understand environment, tooling, and compliance expectations.
- **Code style:** Python 3.13+, type hints, minimal diffs (avoid drive-by refactors)
- **Docs:** Do not update `README.md`; prefer code and docstrings as the source of truth and keep notes minimal and task-scoped
- **Commits:** Commit early and often — prefer many small, focused commits with clear `[TYPE]` messages and concise descriptions.
- **Test:** Do not add/build tests unless explicitly requested. When requested, run via `uv sync --group ci && uv run pytest`.

---

## PixelArch Info
- **PixelArch Tooling:** `yay`, `gh`, and `git` are always installed in PixelArch—avoid adding auto-install or alternate toolchain paths for them
- **PixelArch Packages:** On PixelArch, use `yay` for installs/updates (for example `yay -Syu`). Only use `pacman` if the task explicitly requires it and you say why.

---

## Config & Data Directories

- `~/.midoriai`: App data folder for this program (and other Midori AI programs)
- `~/.midoriai/agents-runner/config.toml`: App + subsystem settings (source of truth) and `[midori_ai_logger]` configuration (create on first run / if missing and fully populate defaults for user edits).
- `~/.codex`: Codex agent config folder (read-write)
- `~/.copilot`: Copilot config folder (read-write)
- `~/.claude`: Claude agent config folder (read-write)
- `~/.gemini`: Gemini CLI config folder (read-write)

---

## Development Basics

- Run locally (GUI): `uv run main.py`
- Follow existing code style: Python 3.13+, type hints throughout, and minimal modifications (avoid drive-by refactors).
- Verification-first: confirm current behavior in the codebase before changing code; reproduce/confirm the issue (or missing behavior); verify the fix with clear checks.
- No broad fallbacks: do not add “fallback behavior everywhere”; only add a narrow fallback when the task explicitly requires it, and justify it.
- No backward compatibility shims by default: do not preserve old code paths “just in case”; only add compatibility layers when the task explicitly requires it.
- Minimal documentation, minimal logging: prefer reading code and docstrings; do not add docs/logs unless required to diagnose a specific issue or prevent a crash.
- Do not update `README.md`.
- Avoid monolith files: **soft max 500 lines per file**, **hard max 1000 lines per file** (split modules/classes when approaching the soft limit).
- Use structured commit messages: `[TYPE] Concise summary`
- Break large changes into reviewable commits.
- Versioning: use 4-part `MAJOR.MINOR.BUILD.TASK` in `pyproject.toml` `project.version` (example `0.1.12.345`). When you move task files from `.agents/tasks/wip/` to `.agents/tasks/done/`, bump `TASK` by `+1` per file moved (if multiple are completed at once, bump by that count). If no task file is moved, do not bump the version unless explicitly instructed. When `TASK` would reach `100000`, reset it to `0` and bump `BUILD` by `+1`. Only bump `MINOR`/`MAJOR` intentionally and reset lower fields to `0`.
- Keep `main.py` as a thin dispatcher (the “main module”):
  - Parse arguments.
  - Route to one package-level entry function.
  - Do not put business logic in `main.py`.

- Organize the code as subsystem packages and subpackages (not a single giant file):
  - All user-facing UI code lives under `agents_runner/ui/` (pages, widgets, styling, themes). Keep Qt isolated there: non-UI subsystems must not import Qt so a headless runner stays possible.
  - Use a top-level supervisor subsystem for orchestration (e.g. `agents_runner/supervisor/`), and let it depend on the task subsystem (e.g. `agents_runner/tasks/`) as needed.
  - Pass data between subsystems via Pydantic models (avoid ad-hoc dicts/tuples).
  - Each subsystem package exposes one clear entry function used by `main.py` for routing (for example `agents_runner/<subsystem>/cli.py`).
  - Packaging (Hatchling):
    - This repo ships as a single Python distribution (one wheel/sdist) built via Hatchling; internal subsystems are Python packages inside that one distribution (they do not get separate `pyproject.toml` files).
    - Any new importable directory under `agents_runner/` must include an `__init__.py`.
    - After adding/moving packages, verify packaging with `uv build`.

- Configuration:
  - Source of truth is TOML parsed with `tomli` and written with `tomli-w` (no JSON config files, no env-driven config).
  - On first run (or if missing), create `~/.midoriai/agents-runner/config.toml` and fully populate it with defaults for user edits.
  - Config hygiene: load TOML into Pydantic models so missing defaults are added and obsolete keys are removed (by design). Detect changes by re-serializing the canonical config and comparing it to what was loaded; if different (upgrades/migrations or user settings updates), rewrite `config.toml` via atomic replace.
  - Env vars are allowed only for Qt/UI/runtime integration; derive them from TOML settings and apply in-process temporarily and/or only to child process `env` dicts.
- Logging:
  - Use the standardized logger package `midori_ai_logger` for application logging; do not add new ad-hoc logging wrappers/utilities.
  - Avoid `print()` for non-CLI output (exceptions: fatal startup/diagnostics paths); use structured logging instead.
- Keep boundaries explicit:
  - Put core logic in pure functions/classes.
  - Keep side effects (filesystem, subprocess, network, Docker) in narrow adapter modules so they are easy to test.
  - Prefer small, named helpers over long methods; extract repeated logic into functions or classes.
  - Keep reusable logic separate from wiring; compute data first, then apply it in UI/widgets/themes.
  - For new features, add or reuse at least one shared helper instead of duplicating logic.

- Sync CI toolchain (before lint/test/type): `uv sync --group ci`
- Format with Ruff (before every commit): `uv run ruff format .`
- Lint with Ruff (treat failures as blockers): `uv run ruff check .`
- Type-check with basedpyright (strict): `uv run basedpyright`
- Tests:
  - Do not add/build tests unless explicitly requested.
  - If you believe a test is really needed to prevent regressions, ask first (keep it minimal).
  - When tests are requested/approved, prefer package-scoped tests in that package’s `tests/` folder (for example `agents_runner/<subsystem>/tests/`).
  - `agents_runner/tests/` is reserved for full package or full-program/integration tests, and should only be used when explicitly requested.
  - Run via `uv sync --group ci && uv run pytest`.

---

## UI / UX Standards

- Keep app UI chrome sharp/square: don’t use non-`0px` `border-radius` or `addRoundedRect(...)` in app widgets/styles.

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

---

## Agent Run Log (Required)

All contributor modes must use a shared run log at `/tmp/agents-artifacts/agent-output.md`:

- Before starting work (and again before appending), read `/tmp/agents-artifacts/agent-output.md` for user feedback or updated constraints.
- After each run, append a short entry describing: role, task/file(s) involved, intent, actions taken, results, and any task file moves (for example `wip/ → done/`, `done/ → wip/`, `done/ → taskmaster/`, or deleted).
- Create `/tmp/agents-artifacts/agent-output.md` if it does not exist.
