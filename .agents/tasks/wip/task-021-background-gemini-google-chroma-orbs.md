# [UI] Gemini background: Google chroma orbs (background-only)

## Summary
Replace Gemini’s legacy “orbs + shards” background with a Gemini-specific animated background that uses only Google’s four brand colors (blue/red/yellow/green) and smoothly shifts between them.

## Desired look (Gemini)
- Base: deep, neutral-dark background (no “white flash” during theme transition).
- Motion: slow drifting “orbs” (radial gradients) similar to Codex’s soft orbs, but color cycling restricted to Google colors only.
- Color behavior:
  - Each orb picks from the 4 colors and slowly blends to the next chosen color over time.
  - No random extra palette colors (no gray/purple/white accents).
- Subtlety: background stays behind UI; never competes with text/cards.

## Non-goals
- Do not change QSS, typography, layout, widgets, or cards; background-only.
- Do not reuse the legacy shared orb/shard system; implement Gemini’s background as its own code path/state.
- Do not add dependencies.

## Acceptance criteria
- When `agent_cli == "gemini"`, `GlassRoot` draws the Gemini-specific animated background.
- Orb motion and color transitions are smooth (no visible stepping, flashing, or abrupt color swaps).
- Palette is restricted to: `#4285F4` (blue), `#EA4335` (red), `#FBBC04` (yellow), `#34A853` (green).
- Performance: idle CPU remains low; paint remains fast (no per-frame heavy allocations).

## Implementation notes (code pointers)
- Background rendering lives in `agents_runner/ui/graphics.py` (`GlassRoot.paintEvent()` → `GlassRoot._paint_theme()`).
- Add a Gemini-specific background painter, e.g. `GlassRoot._paint_gemini_background(...)`, similar to `codex` and `claude` special-cases.
- Add per-agent animation state in `GlassRoot` for Gemini (separate from legacy `_orbs`):
  - List of “chroma orb” objects: position, velocity (optional), radius, current color index, target color index, and `color_t` (0..1) blend phase.
  - Fixed-timestep or low-frequency timer updates to avoid jitter.
- Keep update frequency modest (e.g. 10 FPS timer with internal fixed-step substepping if needed).

## Manual verification
- Run GUI: `uv run main.py`
- Switch to Gemini and observe for 30–60 seconds:
  - Orbs drift slowly
  - Colors blend smoothly and stay within the 4-color palette
  - No popping/poofing on reset; if re-seeding is needed, fade old orbs out rather than clearing instantly

