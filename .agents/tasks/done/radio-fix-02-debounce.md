# radio-fix-02-debounce

## File
`agents_runner/ui/widgets/radio_control.py`

## Summary
Prevent the green→red→green flash that happens between songs when the audio
backend briefly reports "no track." Add a debounce timer so the icon only fades
to idle red if playback truly stopped (user intent) -- not for the auto-gap
between tracks.

## Changes

1. Add `_desired_playing` (bool) field, default `False`, initialized in `__init__`
   alongside `_is_playing` (e.g. line 54 area).

2. Add `_debounce_stop_timer` (QTimer, singleShot, 2-3s interval) whose
   timeout handler calls `_refresh_play_button_icon()` and updates
   `_last_rendered_rgb` to target idle red.

3. Add `set_desired_playing(desired: bool)` public method:
   - Stores `_desired_playing = desired`.

4. Modify `set_playing(playing: bool)`:
   - If `playing` is True:
     - Cancel `_debounce_stop_timer`.
     - Set `_is_playing = True`, `_play_button.setChecked(True)`.
     - Call `_refresh_play_button_icon()` (fades/animates to green).
   - If `playing` is False:
     - If `_desired_playing` is True (auto-gap between tracks):
       - Start `_debounce_stop_timer` (do NOT call `_refresh_play_button_icon` yet).
       - Return early.
     - If `_desired_playing` is False (user stopped):
       - Cancel `_debounce_stop_timer`.
       - Set `_is_playing = False`, `_play_button.setChecked(False)`.
       - Call `_refresh_play_button_icon()` (fades to idle red).

5. When debounce timer fires:
    - Set `_is_playing = False`, `_play_button.setChecked(False)`.
    - Set `_last_rendered_rgb` to `ICON_COLOR_IDLE` (so the color-fade animation
      from radio-fix-01 transitions smoothly from wherever the icon was).
    - Call `_refresh_play_button_icon()` (fade to idle red).
    - Call `_refresh_tooltip()`. After debounce fires the playback state is fully
      stopped — the tooltip must reflect that, matching `set_playing` behavior.

6. In `set_connection_state("reconnecting")`:
   - Cancel `_debounce_stop_timer` immediately.

## Acceptance
- Between songs: icon stays green through the gap (debounce holds).
- After debounce timeout with no new track → fades to red.
- User manually stops: immediate fade to red (no debounce wait).
- Starting playback during debounce: debounce cancelled, immediate green.
- Reconnect state cancels any pending debounce.
