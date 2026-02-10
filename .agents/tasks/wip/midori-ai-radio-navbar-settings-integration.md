# Task: Midori AI Radio Integration for Agents Runner (Navbar + Settings + Resilient Availability)

## Task Status
- `state`: `wip`
- `priority`: `high`
- `created`: `2026-02-10`
- `updated`: `2026-02-10`
- `owner`: `unassigned`
- `related_area`: `agents_runner/ui`

---

## 1) Context and Intent

Add Midori AI Radio to the Agents Runner desktop UI as a first-class but optional subsystem. The goal is to provide a compact radio control on the right side of the top navigation bar, with real stream playback support, and a dedicated Radio settings pane.

This integration must be resilient to service instability (DNS/API outages expected), must avoid crashing or degrading core app behavior, and must follow explicit visibility rules:

- If Qt media capability fails to initialize: hide radio UI and radio settings pane.
- If network/API/DNS fails: keep radio UI and settings visible, show unavailable/degraded state.

The implementation must be decision-complete based on the confirmed behavior below and should not require product decisions during coding.

---

## 2) Product Goals

1. Add a right-side navbar radio control with:
- Music note icon button.
- Hover expansion animation that shifts button left and reveals a volume slider.
- Draggable volume knob.
- Delayed collapse after hover/interaction ends.

2. Support real audio playback from Midori AI Radio stream API:
- Base URL: `https://radio.midori-ai.xyz`
- Stream endpoint: `/radio/v1/stream?q=<quality>`

3. Add radio metadata display behavior:
- Poll current track and append to window title as:
  - `Midori AI Agents Runner - <Track>`

4. Add dedicated Radio settings controls:
- Enable/disable radio.
- Stream quality selector (`low|medium|high`, default `medium`).
- Volume persistence (default `70`).

5. Provide robust availability behavior:
- Heartbeat-based health polling.
- Graceful handling of DNS/API failures.
- No autoplay unless user has explicitly enabled radio or clicked the note control.

---

## 3) Non-Goals (V1)

1. No playlist browsing UI in navbar/settings.
2. No rich metadata panel (album art, artist bio, history view).
3. No per-track explicit quality switch prompt dialogs.
4. No blocking startup on radio reachability.
5. No additional tests unless explicitly requested by task owner.

---

## 4) Confirmed Decisions (Locked)

### 4.1 Visibility and Failure Rules
1. Hide radio navbar control and radio settings pane only when Qt media subsystem fails to initialize.
2. Do not hide radio UI on network health failure or DNS failure.
3. During network/API outages, show unavailable/degraded state while keeping UI visible.

### 4.2 Playback and Activation
1. Real streaming in v1 (not metadata-only).
2. Default autoplay is `off`.
3. Playback begins only if:
- User enables radio via settings, or
- User clicks music note control.
4. Music note button tooltip should make it clear click starts radio system when currently disabled/off.

### 4.3 Polling Cadence
1. Health polling: every `30s`.
2. Current track polling: every `10s`.
3. Run startup health check immediately at initialization.

### 4.4 Quality + Volume
1. Quality options: `low`, `medium`, `high`.
2. Default quality: `medium`.
3. Quality UI location: settings-only.
4. If quality changes while actively playing:
- Preferred behavior: apply on next track boundary.
- Fallback behavior: apply on next play if boundary cannot be reliably detected.
5. Volume default: `70%`.
6. Volume changes persist across launches.

### 4.5 Title Behavior
1. Base title: `Midori AI Agents Runner`.
2. If track available:
- `Midori AI Agents Runner - <Track>`
3. If no track:
- Revert to base title.

---

## 5) API Contract and External Dependencies

### 5.1 Base URL
- `https://radio.midori-ai.xyz`

### 5.2 Endpoints
1. `GET /health`
2. `GET /radio/v1/tracks`
3. `GET /radio/v1/current`
4. `GET /radio/v1/stream?q=<low|medium|high>` (default `medium`)

### 5.3 Envelope Contract (Provided Handoff)
```json
{
  "version": "radio.v1",
  "ok": "boolean",
  "now": "RFC3339 timestamp string",
  "data": "object|null",
  "error": {
    "code": "string",
    "message": "string"
  }
}
```

### 5.4 Availability Reality
Current environment has proven DNS outage behavior (`Could not resolve host`). Implementation must treat this as expected runtime variance, not as a fatal condition.

---

## 6) Settings Contract (State Keys)

Add the following settings keys into `_settings_data`, load defaults, save/apply logic, and Settings UI:

1. `radio_enabled: bool`
- Default: `false`
- Meaning: whether radio playback is user-enabled.

2. `radio_quality: str`
- Allowed: `low`, `medium`, `high`
- Default: `medium`

3. `radio_volume: int`
- Range: `0..100`
- Default: `70`

All keys must survive app restart via existing state persistence pipeline.

---

## 7) UI Requirements

### 7.1 Navbar Control Placement
1. Place radio control in `MainWindow` top header row on the right side.
2. Existing nav buttons remain unchanged: Home, New task, Environments, Settings.
3. Radio control should appear after the existing `addStretch(1)` region, visually anchored to the right.

### 7.2 Navbar Control Interaction
1. Default collapsed state:
- Shows note icon button only.
2. Hover/focus/interaction expanded state:
- Button slides slightly left.
- Volume slider becomes visible.
3. Expanded state persists while:
- Slider is hovered/focused.
- Slider drag is active.
4. Collapse behavior:
- Delayed collapse timer after mouse/focus leaves.
- Cancel collapse if interaction resumes before timer fires.

### 7.3 States and Feedback
Define explicit visual/tooltip states:
1. `qt_unavailable`:
- Control hidden entirely (and settings pane hidden).
2. `service_unavailable`:
- Control visible.
- Playback action disabled or no-op with clear tooltip/status text.
3. `idle_ready`:
- Service healthy; not currently playing.
4. `playing`:
- Active stream playback.

---

## 8) Architecture and Module Plan

### 8.1 New UI Modules (Proposed)
1. `agents_runner/ui/radio/controller.py`
- Owns radio state, Qt media objects, timers, endpoint interactions, and event emissions.

2. `agents_runner/ui/widgets/radio_control.py`
- Owns radio navbar widget visuals and local interaction animation behavior.

3. `agents_runner/ui/radio/__init__.py`
- Expose controller contract for import clarity.

All Qt media logic remains under `agents_runner/ui/` boundary.

### 8.2 Main Window Integration
Update:
- `agents_runner/ui/main_window.py`

Responsibilities:
1. Instantiate controller.
2. Instantiate and insert navbar control widget.
3. Bridge controller state to widget state.
4. Bridge widget actions to controller commands.
5. Update title suffix from current track.
6. Respect Qt capability gating for radio widget visibility.

---

## 9) File-by-File Implementation Breakdown

## 9.1 `agents_runner/ui/main_window.py`
1. Add imports for radio controller/widget.
2. Extend `_settings_data` defaults with:
- `radio_enabled: False`
- `radio_quality: "medium"`
- `radio_volume: 70`
3. Build radio UI control in top layout.
4. Connect events:
- click -> play/toggle behavior.
- slider -> set volume.
5. Subscribe to controller state updates:
- health/status
- playing state
- current track
6. Update window title helper:
- Base title fallback.
- Track suffix formatting.

## 9.2 `agents_runner/ui/main_window_settings.py`
1. In `_apply_settings`, normalize and clamp:
- `radio_enabled` to bool
- `radio_quality` to one of `low|medium|high` (default medium)
- `radio_volume` to int clamped `0..100` (default 70)
2. After apply, push updated settings into controller (if initialized).

## 9.3 `agents_runner/ui/main_window_persistence.py`
1. In `_load_state`, add `setdefault` keys:
- `radio_enabled`
- `radio_quality`
- `radio_volume`
2. Keep backward compatibility by safe defaults only (no broad shims).

## 9.4 `agents_runner/ui/pages/settings_form.py`
1. Extend pane specs with `radio`.
2. Build radio pane controls:
- Enable radio checkbox.
- Stream quality combo.
- Volume slider.
3. Include radio fields in:
- `set_settings(...)`
- `get_settings(...)`
4. Keep pane omitted when Qt media init failure is detected (capability flag path).

## 9.5 `agents_runner/ui/pages/settings.py`
1. Register autosave signals for new radio controls.
2. Ensure immediate/debounced save semantics match existing conventions.

## 9.6 `agents_runner/ui/style/template_base.py` (if needed)
1. Add minimal style selectors for radio control widget and slider.
2. Respect UI standard of square corners (no non-zero border-radius for app chrome).

## 9.7 New module: `agents_runner/ui/radio/controller.py`
Responsibilities:
1. Capability check:
- Validate Qt multimedia constructability at startup.
- Set `qt_available` capability flag.
2. Media setup:
- `QAudioOutput`
- `QMediaPlayer`
3. Timers:
- Health timer @ 30s.
- Current-track timer @ 10s.
4. Network checks:
- Non-blocking behavior.
- Defensive parse of JSON payload.
5. Stream URL building from quality.
6. Playback control API:
- `start_playback()`
- `stop_playback()`
- `toggle_playback()`
- `set_volume(percent)`
- `set_quality(value)`
- `set_enabled(bool)`
7. Quality change staging:
- Store pending quality while playing.
- Apply at next track boundary when detectable.
- Fallback apply-on-next-play.
8. State signaling:
- health availability changes.
- track changes.
- playback state.
- user-facing status text.

## 9.8 New module: `agents_runner/ui/widgets/radio_control.py`
Responsibilities:
1. Render icon button + hidden slider container.
2. Hover enter/leave handling.
3. Expansion/collapse animation.
4. Collapse delay timer logic.
5. Drag-aware interaction lock.
6. Public methods for state display:
- set service available/unavailable
- set playing indicator
- set volume
- set tooltips/status hints

---

## 10) State Machine (Behavioral)

## 10.1 Capability Axis
1. `qt_capable = false`
- hide radio navbar + settings pane.
2. `qt_capable = true`
- show radio navbar + settings pane.

## 10.2 Service Axis
1. `service_available = true`
- enable playback controls.
2. `service_available = false`
- keep visible, mark unavailable/degraded, preserve settings access.

## 10.3 Playback Axis
1. `radio_enabled = false`, not playing.
2. `radio_enabled = true`, idle.
3. `radio_enabled = true`, playing.

Transitions:
1. click note while disabled -> enable + start.
2. click note while idle -> start.
3. click note while playing -> stop/pause (single behavior to be implemented consistently).

---

## 11) Error Handling and Resilience

1. DNS errors:
- do not raise user-facing crashes.
- mark service unavailable.
- retry on next heartbeat.

2. Invalid JSON envelope:
- treat as unavailable for that poll cycle.
- continue timers.

3. Stream startup failure:
- show status text/tooltip.
- remain interactive for retry.

4. Qt media exceptions:
- fail capability probe.
- hide radio UI and settings pane cleanly.

5. Logging:
- concise and structured.
- avoid noisy repeated identical error spam.

---

## 12) Verification Plan (Implementation Acceptance)

## 12.1 Functional Acceptance Criteria
1. Radio icon appears on right side of navbar when Qt media is available.
2. Hover animation expands with left slide + volume slider reveal.
3. Collapse occurs with delay and does not interrupt active drag.
4. Radio stays off at first run unless user enables setting or clicks icon.
5. Settings pane exposes enable + quality + volume controls.
6. Quality defaults to medium, volume defaults to 70.
7. Changes persist across restart.
8. During DNS outage:
- radio UI still visible,
- settings pane still visible,
- status indicates unavailable.
9. Title shows `Midori AI Agents Runner - <Track>` when current track exists.
10. Title reverts to base when track unknown/unavailable.
11. On Qt capability failure:
- radio navbar hidden,
- radio settings pane hidden,
- app otherwise stable.

## 12.2 Manual Scenario Matrix
1. Healthy startup and idle state.
2. Healthy startup and user click-to-play.
3. Service outage at startup.
4. Service outage mid-session (healthy -> fail).
5. Service recovery mid-session (fail -> healthy).
6. Quality switch while playing (boundary apply).
7. Quality switch while playing when boundary not detected (fallback next play).
8. Volume drag at collapsed/expanded transitions.
9. Rapid hover enter/leave stress.
10. App close while playing and reopen.

## 12.3 Regression Checks
1. Existing nav buttons still route correctly.
2. Existing settings autosave behavior unchanged.
3. No interference with task launch flows.
4. No startup slowdown from blocking network calls.

---

## 13) Operational Notes for Implementer

1. Keep core logic in helper/controller classes; do not bloat `main_window.py`.
2. Keep Qt-only logic in UI package boundaries.
3. Maintain minimal-diff discipline.
4. Do not update `README.md`.
5. Do not add tests unless specifically requested.
6. Run formatting/lint only if code edits are made as part of implementation task:
- `uv run ruff format .`
- `uv run ruff check .`

---

## 14) Suggested Implementation Sequence

1. Add controller module with capability probe + timers + playback API.
2. Add radio widget module with hover/slider UX.
3. Integrate widget/controller in `MainWindow`.
4. Add settings keys defaults and normalization.
5. Add Radio settings pane UI and autosave wiring.
6. Add title suffix update hook from track polling.
7. Validate outage behavior and visibility matrix.
8. Final polish for tooltips and state text.

---

## 15) Risk Register

1. `Risk`: Qt multimedia backend differences across host/container.
- `Mitigation`: capability probe + hard hide on probe failure.

2. `Risk`: DNS flapping creates noisy state churn.
- `Mitigation`: debounce visible state transitions and throttle logs.

3. `Risk`: Track boundary detection ambiguity.
- `Mitigation`: staged quality with explicit fallback to next-play.

4. `Risk`: Hover animation fighting with drag events.
- `Mitigation`: drag-aware collapse guard and delayed collapse timer.

---

## 16) Completion Definition

This task is complete when:
1. A user can discover and operate Midori AI Radio via navbar control and settings pane.
2. Default behavior is safe (no autoplay).
3. Volume and quality persist.
4. Track title suffix updates correctly.
5. DNS/API outages do not remove radio UI/settings and do not destabilize app.
6. Qt media init failure cleanly suppresses radio UI/settings only.
7. Core app workflows remain unaffected.

