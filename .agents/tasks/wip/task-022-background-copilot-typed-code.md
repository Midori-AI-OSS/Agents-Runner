# [UI] Copilot background: typed code overlay (background-only)

## Summary
Replace Copilot’s legacy “orbs + shards” background with a Copilot-specific animated background that shows code being “typed” in the background and fading out over time.

## Desired look (Copilot)
- Base: GitHub-dark neutral (`#0D1117`-like), low-contrast texture/vignette ok.
- Foreground effect: monospaced code lines that appear as if typed character-by-character, then gently fade out (never “poof”).
- Color: primary neon green text, with optional occasional accent variants (e.g. purple, a Midori red accent) used sparingly to avoid noise.
- Subtlety: maintain strong readability for UI cards; keep overlay alpha conservative.

## Content sourcing
- Code snippets can be sourced from local repository Python files at random.
- Safety/cleanliness constraints:
  - Source only from workspace code (e.g. `agents_runner/**/*.py`, `main.py`).
  - Exclude `.agents/**`, `.venv*/**`, and any hidden/credential-like files.
  - Strip/skip lines that look like secrets (tokens/keys) if encountered.
  - Prefer short lines; clamp line length and line count per burst.

## Non-goals
- Do not implement full syntax highlighting.
- Do not change QSS or widget styling; background-only.
- Do not reuse the legacy shared orb/shard system.
- Do not add dependencies.

## Acceptance criteria
- When `agent_cli == "copilot"`, `GlassRoot` draws the Copilot-specific animated background.
- Typed lines animate smoothly (no visible character “jumping” due to layout changes).
- All elements fade out; nothing disappears abruptly.
- Rendering remains performant (use caching where sensible; avoid rebuilding large text layouts every paint).

## Implementation notes (code pointers)
- Background rendering lives in `agents_runner/ui/graphics.py` (`GlassRoot.paintEvent()` → `GlassRoot._paint_theme()`).
- Add a Copilot-specific background painter, e.g. `GlassRoot._paint_copilot_background(...)`.
- Suggested implementation approach:
  - Maintain a small list of “typed line” objects with: text, position, `typed_chars`, `age_s`, `hold_s`, `fade_s`, and `color`.
  - Update at a steady tick rate (e.g. 10–20 FPS) and type at a controlled characters-per-second rate.
  - Precompute snippets in the update tick (not during paint) and clamp memory growth.
  - Use a monospaced font and stable line height; optionally use `QStaticText` for completed lines to reduce repeated shaping.

## Manual verification
- Run GUI: `uv run main.py`
- Switch to Copilot and observe:
  - Code appears and types smoothly
  - Older code fades away gradually
  - The effect stays subtle behind cards and does not reduce readability

