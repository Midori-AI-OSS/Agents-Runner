# radio-fix-03-main-window

## File
`agents_runner/ui/main_window.py`

## Summary
Wire the `desired_playing` flag from the radio controller's state snapshot
into the `RadioControlWidget` so the debounce logic in Task 2 can distinguish
user-stopped from between-track gaps.

## Change

In `_on_radio_state_changed()` (around line 440-443, inside the `if qt_available:` block),
add **one line**:

```python
self._radio_control.set_desired_playing(bool(snapshot.get("desired_playing")))
```

Placement: after `set_radio_enabled(...)` and before `set_volume(...)`. Anywhere
inside the `if qt_available:` block is fine as long as it runs after the
existing setters that don't depend on it.

## Acceptance
- `desired_playing` flag flows from `RadioController.state_snapshot()` →
  `RadioControlWidget` on every state change.
- No other code modified.
