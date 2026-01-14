# Task 020-6: Integrate Codex background into theme selection

## Parent Task
task-020-background-codex-cloud-bands

## Description
Modify the theme painting logic to route to the new Codex-specific background when appropriate.

## Specific Actions
- Locate `_paint_theme()` method in GlassRoot
- Add conditional logic to detect when `agent_cli == "codex"`
  - Check how agent_cli is currently accessed (likely from config or theme object)
- When Codex is detected:
  - Call `_paint_codex_background()` instead of default background
  - Skip orbs, polygons, and other default background elements
- For all other agents (Claude, Copilot, Gemini):
  - Keep existing background rendering unchanged
- Test switching between different agent types to ensure correct background is shown

## Code Location
`agents_runner/ui/graphics.py` - Modify `GlassRoot._paint_theme()` method

## Technical Context
- Current `_paint_theme()` at line 369: fills base, paints orbs, paints shards
- Theme system: `self._theme` holds current `_AgentTheme` (line 198)
- Theme name accessed via `self._theme.name` (string: "codex", "copilot", "claude", "gemini")
- Agent detection: check `self._theme.name == "codex"`
- Must preserve theme transition animation (`_theme_to`, `_theme_blend` system at line 403-410)

## Implementation Notes
- Modify `_paint_theme(painter, theme)` method
- Add conditional at start of method:
  ```python
  if theme.name == "codex":
      self._paint_codex_background(painter, self.rect())
      return  # Skip orbs and shards for Codex
  ```
- Keep existing code path for other agents unchanged
- Ensure `_darken_overlay_alpha()` is still applied in `paintEvent()` (line 399-401)
- Test theme switching: codex ↔ copilot, codex ↔ claude, codex ↔ gemini
- Theme transition animation should still work (verify `_theme_blend` renders correctly)

## Dependencies
- Task 020-5 (Codex paint method)

## Acceptance Criteria
- Codex shows new two-band animated background
- Other agents (Claude, Copilot, Gemini) show unchanged backgrounds
- No errors when switching between agent types
- Agent detection logic is clean and maintainable
- Theme transition animation still works smoothly
- Dark overlay (`_darken_overlay_alpha`) still applies correctly
