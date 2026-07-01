# radio-fix-01-color-fade

## File
`agents_runner/ui/widgets/radio_control.py`

## Summary
Add smooth color-fade animation to the play button icon so the green/red transition
does not snap instantly when playback changes or between tracks.

## Changes

1. Add `_last_rendered_rgb` field (tuple[int, int, int] | None) initialized to `None`.

2. Add `_icon_color_anim` (QVariantAnimation) in `__init__`:
   - duration 400-600ms, `QEasingCurve.Type.OutCubic`
   - `valueChanged` → on tick: compute interpolated QColor from
     `_last_rendered_rgb` → target rgb, call `_refresh_play_button_icon()`
   - Add `_first_render` bool guard; the first `_refresh_play_button_icon()`
     call in `__init__` sets the icon directly (no animation).

3. Modify `_refresh_play_button_icon()`:
   - Compute desired target color as today (playing=green, idle=red,
     reconnecting=reconnect).
   - If `_first_render` is True: set icon directly, store final rgb in
     `_last_rendered_rgb`, mark `_first_render = False`, return.
   - Determine target rgb as int tuple from the QColor.
   - If `_icon_color_anim` is running: stop it, read the *current interpolated*
     QColor to use as next `_last_rendered_rgb` (smooth redirect).
   - If `_last_rendered_rgb` is None, default to target (no-op instant).
   - If `_last_rendered_rgb == target`: no-op (already at target).
   - Otherwise: set anim start → current `_last_rendered_rgb`, end → target,
     start. On each tick, create a new `QIcon` via `lucide_icon("audio-lines", color=...)`
     and set it on `_play_button`. On finished, set `_last_rendered_rgb = target`.

4. In `set_connection_state("reconnecting")`:
   - Stop and delete `_icon_color_anim` so reconnect animation takes priority.

## Acceptance
- Icon color fades smoothly from green→red and red→green.
- First render is instant (no visible 0→color pop).
- Rapid state changes smoothly redirect mid-animation.
- Reconnect animation still controls its own color without interference.
- No flicker or visual jump.
