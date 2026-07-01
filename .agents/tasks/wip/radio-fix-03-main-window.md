# radio-fix-03-main-window

## File
`agents_runner/ui/main_window.py`

## Summary
Wire the `desired_playing` flag from the radio controller's state snapshot
into the `RadioControlWidget` so the debounce logic in Task 2 can distinguish
user-stopped from between-track gaps.

## Change

In `_on_radio_state_changed()` (around line 440-443, inside the `if qt_available:` block),
add **one line** BEFORE `set_playing(...)`:

```python
self._radio_control.set_desired_playing(bool(snapshot.get("desired_playing")))
```

Placement: after `set_service_available(...)` (line 440) and before `set_playing(...)`
(line 441). Example:

```python
self._radio_control.set_service_available(bool(snapshot.get("service_available")))
self._radio_control.set_desired_playing(bool(snapshot.get("desired_playing")))
self._radio_control.set_playing(bool(snapshot.get("is_playing")))
```

RATIONALE: `set_desired_playing()` MUST be called before `set_playing()` and
`set_connection_state()` so the debounce logic in radio-fix-02 sees the correct
`_desired_playing` value. If `set_playing(False)` runs before
`set_desired_playing(True)`, the icon immediately fades to red instead of
holding green through the debounce window. Order is critical.

## Acceptance
- `desired_playing` flag flows from `RadioController.state_snapshot()` →
  `RadioControlWidget` on every state change.
- No other code modified.
