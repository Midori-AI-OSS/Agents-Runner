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


## Technical Requirements
- Import needed: `from PySide6.QtGui import QLinearGradient` (not currently imported)
- Type hints required: all methods must use Python 3.13+ type annotations
- Performance target: paint method < 5ms, CPU usage < 3% idle
- Timer frequency: 100ms (10 FPS) recommended for balance of smoothness and efficiency
- Color values:
  - Top band: #ADD8E6 (LightBlue) ↔ #FF8C00 (DarkOrange)
  - Bottom band: #2A2A2A ↔ #3A3A3A (specific grays for consistency)
- Gradient: 80px feather above/below boundary, 7 color stops (0.0, 0.15, 0.35, 0.5, 0.65, 0.85, 1.0)
- Phase calculation periods:
  - Split ratio: 45 seconds (oscillates 0.3 to 0.6)
  - Top color blend: 35 seconds (0.0 to 1.0)
  - Bottom color blend: 40 seconds (0.0 to 1.0)

## Integration Points
- Theme transition system: preserve `_theme_blend` animation compatibility (line 403-410)
- Dark overlay: ensure `_darken_overlay_alpha()` still applies correctly (line 399-401)
- Window resize: existing `resizeEvent()` handler should work with new background (line 244)
- Must not interfere with other agent themes (copilot, claude, gemini)
- Current theme accessed via `self._theme.name` (string: "codex", "copilot", "claude", "gemini")

## Subtasks
This parent task is broken down into 9 sequential subtasks (task-020-1 through task-020-9):
1. Animation timer infrastructure (task-020-1)
2. Phase calculation functions (task-020-2)
3. Color blending utilities (task-020-3)
4. Soft boundary gradient renderer (task-020-4)
5. Codex-specific paint method (task-020-5)
6. Integration into theme selection (task-020-6)
7. Visual validation testing (task-020-7)
8. Readability and accessibility testing (task-020-8)
9. Performance optimization (task-020-9)

Each subtask has detailed acceptance criteria and technical context in separate files.

