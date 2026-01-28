# Crash exit 139 — investigation steps (brainstorm)

## Capture more diagnostics

- Run with `AGENTS_RUNNER_FAULTHANDLER=1` and check `~/.midoriai/agents-runner/faulthandler.log`.
- Increase QtWebEngine logging:
  - `QT_LOGGING_RULES="qt.webenginecontext.debug=true;qt.webengine*.debug=true"`
  - Chromium: `QTWEBENGINE_CHROMIUM_FLAGS="--enable-logging=stderr --v=1"`

## Validate GPU/Vulkan hypothesis

- Try disabling GPU explicitly:
  - `QTWEBENGINE_CHROMIUM_FLAGS="--disable-gpu --disable-gpu-compositing --disable-features=Vulkan"`
- If this avoids the crash, adjust runtime detection to handle “`/dev/dri` exists but GBM unusable”.

## Validate fontconfig propagation

- Confirm `FONTCONFIG_FILE` and related env vars are present for the QtWebEngine subprocess.
- Confirm whether the `(null)` error persists when explicitly setting fontconfig env vars.

## Tighten repro

- Use a task with headless desktop enabled so `novnc_url` becomes available.
- Repeatedly switch `Task` ↔ `Desktop` tabs and open/close Task Details from the dashboard.
