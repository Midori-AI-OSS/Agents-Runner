# Add `midoriai` UI theme (darker Codex background)

Policy
- The `midoriai` theme implementation must not import/call any existing agent theme modules (`codex`, `claude`, `copilot`, `gemini`) at runtime.

Issue
- The runner’s background system effectively treats the Codex theme as the “main” default/fallback.
- We want a neutral runner theme named `midoriai`, based on the existing Codex background but darker.

Goal
- Add a `midoriai` theme implementation under `agents_runner/ui/themes/midoriai/`.
- Make `midoriai` the default/fallback background theme for the runner UI.
- Keep changes isolated to `agents_runner/ui/` (Qt-only).

Starting point (current code)
- Theme selection + painting: `agents_runner/ui/graphics.py`
  - `_theme_for_agent(...)`: maps agent_cli → theme name/base.
  - `GlassRoot._darken_overlay_alpha(...)`: final dark overlay per theme.
  - `GlassRoot._paint_theme(...)`: dispatches to theme painters.
  - `GlassRoot._update_background_animation(...)`: drives animated themes + repaint loop.
- Codex background painter: `agents_runner/ui/themes/codex/background.py` (`paint_codex_background`).
- Existing theme packages: `agents_runner/ui/themes/{codex,claude,copilot,gemini}/`.

Proposed approach (minimal)
1) Add a new theme package:
   - `agents_runner/ui/themes/midoriai/__init__.py`
   - `agents_runner/ui/themes/midoriai/background.py`
2) Implement `paint_midoriai_background(...)` by reimplementing the Codex background algorithm (do not call/import the Codex painter at runtime):
   - Use `agents_runner/ui/themes/codex/background.py` as the reference implementation, but copy the logic into `agents_runner/ui/themes/midoriai/background.py` (rename functions/consts as needed).
   - Keep the same public surface area as Codex (`calc_split_ratio`, `calc_top_phase`, `calc_bottom_phase`) so `GlassRoot` can drive the animation the same way.
   - Darken the look by adjusting the palette (top/bottom band blend endpoints + blob colors) and/or applying an extra dark overlay fill at the end.
3) Wire it into `agents_runner/ui/graphics.py`:
   - Import the `midoriai` background module.
   - Switch the runner default/fallback theme from `codex` to `midoriai`.
   - Ensure the animation update loop includes `midoriai` (use `midoriai.background.calc_*` when `midoriai` is active; same repaint behavior as Codex).
   - Add a `_paint_theme` branch for `midoriai` (paint via `paint_midoriai_background`).
   - Add a `_darken_overlay_alpha` branch for `midoriai` (or keep all darkening inside the painter; pick one source of truth).

Notes
- This task is intended to land before `025-unify-runplan-pydantic.md` and `026-agent-system-plugins.md`.
- `026-agent-system-plugins.md` uses `midoriai` as the fallback theme name; this task makes that concrete in the UI.

Subtasks (small, reviewable)
- Add the `midoriai` theme package (initial version: reimplemented Codex algorithm with darker palette).
- Switch UI default/fallback theme name to `midoriai`.
- Manual QA on desktop: verify the background is darker but still readable and animations still update.

Constraints
- Keep UI chrome square (no rounded corners changes).
- Minimal diffs; do not refactor the theme system broadly.

Verify
- `uv run --group lint ruff check .`
- `uv run --group lint ruff format .`
- Manual: `uv run main.py` and confirm the startup background is `midoriai`.
