# [UI] Background system refactor: remove legacy orb/shard renderer

## Summary
After Gemini and Copilot have dedicated backgrounds (Codex and Claude already do), remove the legacy shared “orbs + shards” renderer and migrate fully to per-agent background code paths.

## Motivation
- The legacy background code mixes multiple unrelated visual systems (orbs + shard polygons) and makes per-agent art direction harder.
- A per-agent background renderer keeps each agent’s visual identity isolated and easier to tune.

## Non-goals
- Do not change widget styling/QSS as part of this cleanup.
- Do not add dependencies.

## Acceptance criteria
- No code paths rely on:
  - `_paint_orbs(...)`
  - shard polygons / `_SHARD_POINTS_*`
  - `orb_colors`, `shard_colors`, `shard_points` theme fields
- Each agent theme uses a dedicated background painter in `agents_runner/ui/graphics.py`:
  - `codex` → `_paint_codex_background(...)`
  - `claude` → `_paint_claude_background(...)`
  - `gemini` → `_paint_gemini_background(...)`
  - `copilot` → `_paint_copilot_background(...)`
- Theme transition (`set_agent_theme` with 7s blend) still works without flashes.
- Overlay darkening remains correct per theme.

## Implementation notes
- Simplify `_AgentTheme` to only the fields still required for background selection and overlays.
- Delete unused shard point constants and orb state that are no longer used once all agents are migrated.
- Keep changes minimal and focused; avoid drive-by refactors.

## Manual verification
- Run GUI: `uv run main.py`
- Switch between all agents and watch the 7s transition:
  - No blank frames, no white flashes, no sudden popping artifacts

