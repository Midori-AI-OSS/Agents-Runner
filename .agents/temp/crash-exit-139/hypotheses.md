# Crash exit 139 — hypotheses (brainstorm)

1. QtWebEngine/Chromium GPU path instability: logs mention GBM unsupported and Vulkan fallback; GPU acceleration may remain enabled because `_configure_qtwebengine_runtime()` disables GPU only when `/dev/dri` is absent.
2. Fontconfig initialization issue: `Fontconfig error ... (null)` suggests the QtWebEngine subprocess can’t find config (or env is sanitized). Could be benign or contribute to instability.
3. Navigation timing / widget visibility: `setUrl(...)` happens via `QTimer.singleShot(0, ...)` on tab change; rapid tab switching/task switching might hit a race in QtWebEngine.
4. Repeated `setUrl(about:blank)` during tab hiding: `_sync_desktop()` can switch URLs while hiding; QtWebEngine teardown/reload can be fragile.
5. Two separate “initialization” touches: `_initialize_qtwebengine()` creates/deletes a dummy view; `TaskDetailsPage` creates the real view. Creation/destruction timing may leave partially initialized native state.
6. Desktop tab reload behavior: `_sync_desktop()` navigates to `about:blank` and clears `_desktop_loaded_url` when hidden; returning triggers another `setUrl(...)` and reload.
