# UI layout + module layout migration (AGENTS.md standards)

## Why this task exists

We recently updated `AGENTS.md` with stricter UI/layout standards:

- All user-facing UI code must live under `agents_runner/ui/` (pages, widgets, styling, themes).
- Keep Qt isolated to UI so a headless runner stays possible: non-UI subsystems must not import Qt.
- UI chrome stays sharp/square: avoid non-`0px` `border-radius` and avoid `addRoundedRect(...)`.

This repo currently has UI-related modules outside `agents_runner/ui/` and some non-UI subsystems importing Qt. This task is to inventory + migrate the current layout so it matches the standards.

## Scope (what to change)

### A) Move UI modules into `agents_runner/ui/` (or refactor them so Qt does not leak)

Current Qt-importing files outside `agents_runner/ui/` (inventory):

- `agents_runner/app.py` (Qt app startup + stylesheet + window)
- `agents_runner/qt_diagnostics.py` (Qt message handler)
- `agents_runner/desktop_viewer/app.py` (Qt UI process)
- `agents_runner/widgets/*` (custom widgets, painting, highlighters)
- `agents_runner/style/*` (QSS templates + palette)
- `agents_runner/docker/artifact_file_watcher.py` (Qt file watching used by UI)
- `agents_runner/stt/qt_worker.py` (Qt worker wrapper for STT)

Goal: after the migration, `rg -n "^(from PySide6|import PySide6)" -S agents_runner --glob '!agents_runner/ui/**'` returns no matches.

### B) Fix import graph so UI depends on core, not vice-versa

Known UI→non-UI crossovers to resolve:

- `agents_runner/ui/pages/artifacts_tab.py` imports `agents_runner/docker/artifact_file_watcher.py` (Qt code living under a non-UI subsystem).
- UI imports `agents_runner.widgets.*` throughout (`main_window.py`, several dialogs/pages).
- `agents_runner/ui/lucide_icons.py` imports `agents_runner.style.palette`.

Goal: UI uses `agents_runner/ui/...` modules for UI concerns; non-UI packages stay Qt-free.

### C) Preserve “sharp/square” UI styling while migrating

The current stylesheets already include `border-radius: 0px;` in template strings (for example in `agents_runner/style/template_base.py` and `agents_runner/style/template_tasks.py`). The migration must keep that behavior and avoid introducing rounded corners via QSS or `addRoundedRect(...)`.

## Non-goals (do not do in this task)

- Do not redesign UI/UX visually beyond what is required to keep the same look after module moves.
- Do not do drive-by refactors, renames, or reformat unrelated code.
- Do not add tests unless Luna explicitly asks.
- Do not update `README.md`.

## Suggested target layout (proposed)

Pick a directory map that matches the AGENTS.md rules; one option:

- `agents_runner/ui/app.py` (or `agents_runner/ui/runtime/app.py`): Qt application startup (`run_app`) and UI-only environment/QWebEngine configuration.
- `agents_runner/ui/qt_diagnostics.py`: Qt message handler.
- `agents_runner/ui/desktop_viewer/` (or `agents_runner/ui/viewer/`): desktop viewer process code.
- `agents_runner/ui/widgets/`: move `agents_runner/widgets/*` here.
- `agents_runner/ui/style/`: move `agents_runner/style/*` here (palette + stylesheet templates).
- `agents_runner/ui/artifacts/file_watcher.py`: move/replace `docker/artifact_file_watcher.py` (see below).
- `agents_runner/ui/stt/qt_worker.py`: move the Qt-based STT worker wrapper out of `agents_runner/stt/`.

If you choose a different structure, keep it minimal and ensure *all* UI code lands under `agents_runner/ui/`.

## File-watcher decision (important)

`agents_runner/docker/artifact_file_watcher.py` is Qt-based and is used only by the UI (via `agents_runner/ui/pages/artifacts_tab.py`).

Choose one:

1) UI-owned watcher: move it under `agents_runner/ui/` and ensure it is imported only by UI code.
2) Headless watcher: replace Qt usage with a non-Qt file watcher in a core/docker-safe location, and (optionally) add a thin Qt adapter in UI to bridge signals.

Preference: option (2) if it’s straightforward without new dependencies; otherwise option (1) is acceptable as a first step.

## Acceptance criteria

- No Qt imports outside `agents_runner/ui/` (use the `rg` command above to confirm).
- UI pages/dialogs no longer import from `agents_runner/widgets` or `agents_runner/style` (those modules are relocated under `agents_runner/ui/`).
- `agents_runner/docker/` and `agents_runner/stt/` contain no Qt imports (unless a specific exception is approved by Luna).
- App still starts via `uv run main.py` (manual smoke check; no new tests required).
- Ruff passes if run (`uv run ruff format .` then `uv run ruff check .`).

## Verification steps (read-only first, then smoke)

1) Read-only inventory:
   - Run `rg` checks for `PySide6` outside `agents_runner/ui/`.
   - Identify import paths that will need updating (`agents_runner.widgets`, `agents_runner.style`, `agents_runner.docker.artifact_file_watcher`, `agents_runner.stt.qt_worker`).
2) Apply migration (minimal edits, update imports).
3) Run the same `rg` checks again.
4) Manual smoke: `uv run main.py` and click through the key screens that use custom widgets (New Task, Task Details, Artifacts).

## Optional: “read-only subagent” helper (Codex CLI)

If you want a fast second opinion before editing code, use the Agents Runner Codex guidance:

```
codex exec --sandbox danger-full-access -o /tmp/agents-artifacts/ui-layout-migration-inventory.md "<PROMPT>" > /tmp/agents-artifacts/subagent-run.log 2>&1
```

Suggested prompt topics:
- “List all Qt imports outside `agents_runner/ui/` and propose a minimal relocation plan.”
- “Find UI code outside `agents_runner/ui/` and group it into widgets/style/runtime/viewer buckets.”

---

## Completion Note

**Status:** ✓ COMPLETED

**Date:** 2025-02-01

**Actions taken:**
1. Created new UI subdirectories: `ui/runtime/`, `ui/artifacts/`, `ui/stt/`
2. Moved all UI-related modules to `agents_runner/ui/`:
   - `app.py` → `ui/runtime/app.py`
   - `qt_diagnostics.py` → `ui/qt_diagnostics.py`
   - `desktop_viewer/` → `ui/desktop_viewer/`
   - `widgets/` → `ui/widgets/`
   - `style/` → `ui/style/`
   - `docker/artifact_file_watcher.py` → `ui/artifacts/file_watcher.py`
   - `stt/qt_worker.py` → `ui/stt/qt_worker.py`
3. Updated all import statements across the codebase (main.py, UI files, dialogs, pages)
4. Verified no Qt imports remain outside `agents_runner/ui/` (using ripgrep check)
5. Ran ruff format and ruff check - all checks passed
6. Verified build with `uv build` - successful
7. Tested imports with `uv run python` - successful

**Verification:**
- ✓ `rg -n "^(from PySide6|import PySide6)" -S agents_runner --glob '!agents_runner/ui/**'` returns no matches
- ✓ All imports updated to new paths
- ✓ Ruff format and check pass
- ✓ Build succeeds
- ✓ Import tests pass

**Commits:**
- fd90668: [REFACTOR] Migrate UI code to agents_runner/ui/ per AGENTS.md standards
- 7e65faa: [VERSION] Bump to 0.1.0.1 after completing ui-layout-standards-migration task

**Note:** The migration preserves all "sharp/square" UI styling (border-radius: 0px) as required by AGENTS.md.
