# Task 01: Radio Art Model + Endpoint

## Objective
Add art album-art fetching capability to the RadioController so the dynamic theme can obtain album art URLs.

## Context
The RadioController in `agents_runner/ui/radio/controller.py` currently polls `/radio/v1/current` every 10s via `_poll_current()` → `_handle_current_response()`. Track boundaries are detected in `_handle_current_response()` (line ~667: `boundary_detected = ...`). The controller uses `QNetworkAccessManager` via `_request_json()` for all HTTP calls. State is emitted as a plain dict via `state_changed` signal.

## Work Items

### 1. Create `agents_runner/ui/radio/art_models.py`
- Create a Pydantic `BaseModel` class `ArtPayload` with fields:
  - `art_url: str` — relative URL like `/art/abc123.jpg`
  - `has_art: bool`
  - `track_id: str`
  - `mime: str`
  - `channel: str`
- Do NOT add `__init__.py` changes — the radio package already has one exporting `RadioController`.

### 2. Modify `agents_runner/ui/radio/controller.py`
- Add class constant: `ART_ENDPOINT = "/radio/v1/art"`
- Add internal storage to `__init__`: `self._art_data: dict[str, Any] = {}`
- Add `"art"` key to `state_snapshot()` return dict, populated from `self._art_data`
- Add method `_fetch_art(channel: str) -> None`:
  - Uses `self._request_json(self.ART_ENDPOINT, callback, include_channel=True, channel=channel)`
  - Callback receives `(payload, error_text)`. On success, extract `data = payload.get("data")` (following the existing `_handle_current_response` pattern), then parse into `ArtPayload.model_validate(data)`
  - Resolves relative `art_url` to absolute: if `art_url` does not start with `http`, prepend `self.BASE_URL`
  - Store `art_url`, `has_art`, `track_id`, `mime`, `channel` in `self._art_data`
  - Emit `self._emit_state()` after updating
- In `_handle_current_response()`, after detecting `boundary_detected` (around line 666-672, in the `if boundary_detected:` block), also call `self._fetch_art(resolved_channel)` so art is fetched only on track boundaries — NOT on every poll.
  - Also trigger `_fetch_art` when `resolved_channel` differs from what's in `_art_data.get("channel")` (channel switch detection within `_handle_current_response`). Place this channel-switch check after `resolved_channel` is set (line 658) and before the boundary_detected logic, so a channel switch fetches art immediately even if the track_id hasn't changed yet.
- Add `import` for `ArtPayload` at top of controller.py:
  ```python
  from agents_runner.ui.radio.art_models import ArtPayload
  ```

## Key Constraints
- Do NOT add a polling timer for art. Art fetch is event-driven on track boundary.
- Use `self._request_json()` (existing method) for the HTTP request — follow the same pattern as `_poll_current()`.
- Call `_fetch_art` only after `_set_service_available(True, ...)` has been called and data is confirmed valid.
- Handle errors gracefully — if art fetch fails, set `_art_data = {}` and emit state.

## Verification
- `ArtPayload` can be imported: `from agents_runner.ui.radio.art_models import ArtPayload`
- `state_snapshot()` includes `"art"` key
- Track boundary in `_handle_current_response` triggers `_fetch_art`
- Channel switch triggers `_fetch_art`
- No new timer, no change to polling interval
- `uv run ruff check agents_runner/ui/radio/` passes
