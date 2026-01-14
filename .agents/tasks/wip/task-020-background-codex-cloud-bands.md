# [UI] Codex background: cloud band + drifting split bands

## Summary
Update the Codex (default) app background to a slow-moving, airy two-band composition:
- Top band: a “cloud” area that shifts color between Light Blue and Dark Orange.
- Bottom band: darker gray field that slowly shifts between two dark grays.
- The split between bands should drift slowly from ~30/70 to ~60/40 over time, with soft blending at the boundary.

## Desired look (Codex)
- Top band color cycle: `#ADD8E6` (LightBlue) ↔ `#FF8C00` (DarkOrange), with gentle blending (not hard switching).
- Bottom band cycle: “light-but-still-dark” gray ↔ “darker” gray (choose two close grays that preserve readability).
- Boundary between bands: soft/airy blend (feathered gradient, not a crisp line).
- Motion:
  - Split ratio drifts slowly from 30/70 to 60/40 and back (very slow).
  - Colors drift slowly (very slow).
  - Add subtle randomness so the motion does not feel purely periodic.

## Non-goals (for this task)
- Do not redesign Claude/Copilot/Gemini backgrounds yet (need separate specs).
- Do not add new dependencies.

## Acceptance criteria
- When `agent_cli == "codex"` the background uses the described banded composition.
- Transitions are slow and subtle; no visible “ticking” or rapid movement.
- Boundary blend is visibly soft and “airy”.
- Overall readability remains good (text/cards still readable).

## Implementation notes (code pointers)
- Background is drawn by `GlassRoot` in `agents_runner/ui/graphics.py`:
  - `GlassRoot.paintEvent()`
  - `GlassRoot._paint_theme()`
  - Theme selection via `_theme_for_agent()`
- Current implementation: base fill + orbs + polygon shards. For Codex, either:
  - add a Codex-specific paint path (banded background) and keep other agents unchanged, OR
  - extend `_AgentTheme` with background parameters and implement in a shared renderer.
- Motion: `GlassRoot` currently has animation disabled (`self._animate_orbs = False`).
  - Add a slow timer to update a small set of background phase parameters (split ratio + color blend + small jitter).
  - Keep update frequency low (e.g., a few times per second) and use continuous time functions to avoid stutter.
- Keep “sharp UI” constraint: avoid rounded-rect UI styling and `addRoundedRect(...)`.

