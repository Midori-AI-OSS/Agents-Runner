# Task 05: MainWindow Dynamic Theme Wiring

## Objective
Wire the MainWindow to connect radio state changes to the dynamic theme: when the "dynamic" theme is active and the radio is playing, fetch album art, extract colors, build a `MidoriVariantSpec`, and push it to the dynamic theme background via `set_art_spec()`. When radio stops or has no art, reset to fallback.

## Context
- `MainWindow` in `agents_runner/ui/main_window.py` already has:
  - `_radio_controller: RadioController` (line 198)
  - `_on_radio_state_changed()` method (line 424) connected to `state_changed` signal (line 251)
  - `_settings_data` dict with `"ui_theme"` key (line 111)
  - `self._root = GlassRoot()` (line 200)
  - Imports `RadioController` from `agents_runner.ui.radio` (line 30)
- `_on_radio_state_changed()` currently updates the radio control widget and window title only.
- `GlassRoot.set_theme_name()` handles theme switching (4s crossfade).

## Work Items

### 1. Add imports to `agents_runner/ui/main_window.py`
Add after existing radio import (line 30):
```python
from agents_runner.ui.radio.art_colors import build_dynamic_spec
from agents_runner.ui.radio.art_colors import download_art
from agents_runner.ui.radio.art_colors import extract_dominant_colors
from agents_runner.ui.radio.art_colors import hash_to_style
from agents_runner.ui.themes.dynamic.background import set_art_spec as set_dynamic_art_spec
```
Add at the existing `PySide6.QtGui` import line (currently `QCloseEvent, QResizeEvent`), append `QImage`:
```python
from PySide6.QtGui import QCloseEvent, QImage, QResizeEvent
```
Add import for `normalize_ui_theme_name`:
```python
from agents_runner.ui.graphics import normalize_ui_theme_name
```
Add import for `QNetworkAccessManager`:
```python
from PySide6.QtNetwork import QNetworkAccessManager
```

### 2. Add network manager for art downloads to `__init__`
- In `__init__`, after `self._radio_controller = RadioController(self)`:
```python
self._art_network = QNetworkAccessManager(self)
```
(`QNetworkAccessManager` import added in section 1 above.)

### 3. Add `_active_art_channel` tracker to `__init__`
- In `__init__`, in the `self._` attributes section (around line 137-161):
```python
self._active_art_channel: str = ""
```

### 4. Add dynamic theme handler to `_on_radio_state_changed`
Modify `_on_radio_state_changed()` (line 424). After the existing logic, at the end of the method (before the return or at the bottom), add:

```python
self._update_dynamic_theme_from_radio(state)
```

### 5. Create `_update_dynamic_theme_from_radio` method
Add a new method after `_on_radio_state_changed`:

```python
def _update_dynamic_theme_from_radio(self, state: dict[str, Any]) -> None:
    ui_theme = normalize_ui_theme_name(self._settings_data.get("ui_theme"), allow_auto=False)
    if ui_theme != "dynamic":
        return

    is_playing = bool(state.get("is_playing"))
    art_data = state.get("art")
    if isinstance(art_data, dict):
        art_url = str(art_data.get("art_url") or "").strip()
        track_title = str(state.get("current_track") or "").strip()
        has_art = bool(art_data.get("has_art"))
        art_channel = str(art_data.get("channel") or "").strip()
    else:
        art_url = ""
        track_title = ""
        has_art = False
        art_channel = ""

    if not is_playing or not has_art or not art_url:
        set_dynamic_art_spec(None, "")
        self._active_art_channel = ""
        return

    if art_channel == self._active_art_channel and art_url:
        return

    self._active_art_channel = art_channel
    style = hash_to_style(track_title) if track_title else "blobs"

    def _on_art_downloaded(image: QImage | None) -> None:
        if image is None or image.isNull():
            set_dynamic_art_spec(None, "")
            return
        colors = extract_dominant_colors(image, n=4)
        spec = build_dynamic_spec(colors, style)
        set_dynamic_art_spec(spec, style)

    download_art(art_url, self._art_network, _on_art_downloaded)
```

## Key Constraints
- Do NOT call `set_theme_name()` on `GlassRoot` per track change — the theme stays "dynamic" always. Only `set_art_spec()` is called.
- Art download uses `QNetworkAccessManager` (async, non-blocking callback). NEVER use Pillow/urllib/requests.
- On channel switch: immediately apply new art (the `_active_art_channel` check prevents redundant fetches).
- When radio is not playing or has no art: call `set_art_spec(None, "")` to fall back to dark spec.
- The `_on_art_downloaded` callback captures `style` from the enclosing scope (closure) — that's fine since `hash_to_style` is deterministic.
- `QNetworkAccessManager` instance `_art_network` must be parented to `self` (MainWindow) so it's cleaned up properly.
- Thread safety: `set_art_spec` already has `threading.Lock` protection (from Task 03).

## Verification
- When `ui_theme == "dynamic"` and radio plays, `_update_dynamic_theme_from_radio` is called
- `set_art_spec(None, "")` is called when radio stops or has no art
- `set_art_spec(spec, style)` is called when art is downloaded and colors extracted
- No `set_theme_name()` is called from this handler
- `_art_network` is a `QNetworkAccessManager` parented to MainWindow
- `uv run ruff check agents_runner/ui/main_window.py` passes
