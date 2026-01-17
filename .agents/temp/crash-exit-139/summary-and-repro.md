# Crash exit 139 — summary + symptoms + repro hints (brainstorm)

## Summary

The GUI sometimes terminates with exit code `139` (SIGSEGV) while opening a task or switching to the `Desktop` tab. This appears correlated with QtWebEngine (`QWebEngineView`) navigation (`setUrl(...)`) and/or GPU/fontconfig setup during Chromium initialization.

This is investigation + stabilization planning only (no fixes here).

## Observed symptoms / repro hints

- Chromium/QtWebEngine startup messages observed:
  - `GBM is not supported with the current configuration. Fallback to Vulkan rendering in Chromium.`
  - `Fontconfig error: Cannot load default config file: No such file: (null)`
- Crash triggers reported:
  - Selecting/opening a task in the dashboard (transitions to Task Details view).
  - Clicking the `Desktop` tab (noVNC embed) or switching back/forth between tabs.
- Exit code `139` implies a hard crash (native segfault); Python exceptions may not surface.
