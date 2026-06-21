# Task 06: Soften Dynamic Theme Transitions + Rename

## Objective
Fix aggressive flashing when radio turns on/off, station changes, and song changes. Rename theme label to "Dynamic Music".

## Context
The dynamic theme's `_transition_duration` is 2.0s and `set_art_spec(None, "")` immediately drops to dark fallback. The hold mechanism and transition fixes live entirely in `background.py`.

## Work Items

### 1. `agents_runner/ui/pages/settings_form.py`
- Line ~1233-1234: Change `"Dynamic (Radio)"` → `"Dynamic Music"`

### 2. `agents_runner/ui/themes/dynamic/background.py`

**a) Increase transition duration**
- `_transition_duration = 2.0` → `_transition_duration = 4.0`

**b) Add hold mechanism state**
Add after existing module-level state:
```python
_last_valid_spec: MidoriVariantSpec | None = None
_last_valid_time: float = 0.0
_hold_duration: float = 8.0
```

**c) Fix `set_art_spec()`**
- When spec is NOT None: save to `_last_valid_spec = spec`, `_last_valid_time = time.monotonic()`
- When spec IS None: set style to `"blobs"` (not empty string `""`)

**d) Fix `paint()` blend_factor + hold logic**
Current code (lines 334-346) reads state and computes blend_factor from `_transition_start_s`. Replace the blend_factor computation to handle hold:
- If `current is None`:
  - If `_last_valid_spec` is not None AND `time.monotonic() - _last_valid_time < _hold_duration`:
    - `resolved = _last_valid_spec`, `blend_factor = 0.0` (freeze during hold)
  - Else:
    - `resolved = _FALLBACK_SPEC`
    - `blend_factor = clamp((now - (_last_valid_time + _hold_duration)) / _transition_duration, 0, 1)`
- Else (current is not None):
  - `resolved = current`
  - `blend_factor = clamp((now - t_start) / _transition_duration, 0, 1)` IF t_start and previous exist, else `1.0`

Read ALL needed state (`_last_valid_spec`, `_last_valid_time`) under the existing `_lock`.

**e) Add `reset_dynamic_state()` function**
```python
def reset_dynamic_state() -> None:
    """Reset hold state when user switches away from dynamic theme."""
    global _last_valid_spec, _last_valid_time
    with _lock:
        _last_valid_spec = None
        _last_valid_time = 0.0
```

### 3. `agents_runner/ui/main_window.py`

**a) Add `_has_dynamic_spec` tracker to `__init__`**
```python
self._has_dynamic_spec: bool = False
```

**b) Replace dedup (line ~475) with conditional dedup**
```python
if art_channel == self._active_art_channel and art_url and self._has_dynamic_spec:
    return
```

**c) In `_on_art_downloaded` callback:** set `self._has_dynamic_spec = True` after successful `set_dynamic_art_spec(spec, style)`

**d) In the `not is_playing or not has_art` path:** set `self._has_dynamic_spec = False` before calling `set_dynamic_art_spec(None, "blobs")`

**e) Add theme-switch cleanup (`ui_theme != "dynamic"` early return)**
At the early return (line ~454): 
```python
if ui_theme != "dynamic":
    if self._has_dynamic_spec:
        reset_dynamic_state()
        self._has_dynamic_spec = False
    return
```

**f) Add import for `reset_dynamic_state`**
```python
from agents_runner.ui.themes.dynamic.background import reset_dynamic_state
from agents_runner.ui.themes.dynamic.background import set_art_spec as set_dynamic_art_spec
```
(Merge with existing `set_art_spec` import line)

**g) Do NOT add QTimer** — hold mechanism in background.py handles all timing.

### 4. `agents_runner/ui/radio/art_colors.py`
- In `build_dynamic_spec()`: change `ambient_overlay` alpha from 34 → 50
  - `ambient_overlay = QColor(0, 0, 0, 50)`

## Key Constraints
- No QTimer — hold-only approach in background.py
- `_last_valid_spec` and `_last_valid_time` must be read/written under the existing `_lock`
- Blend_factor must FREEZE at 0.0 during hold (don't advance), then start from 0.0 at hold expiry
- Theme-switch cleanup: call `reset_dynamic_state()` when leaving "dynamic" theme
- Keep download-failure `set_dynamic_art_spec(None)` calls — the hold protects visually

## Verification
- `uv run ruff check agents_runner/ui/themes/dynamic/ agents_runner/ui/main_window.py agents_runner/ui/pages/settings_form.py agents_runner/ui/radio/art_colors.py` passes
- `_format_theme_label("dynamic")` returns `"Dynamic Music"`
- `BACKGROUND.base_color()` returns Midori AI Dark fallback when no spec is set
- After `set_art_spec(None, "blobs")`, `paint()` uses `_last_valid_spec` for 8s then crossfades to `_FALLBACK_SPEC`
