# Task — Investigate and fix crash exit 139 (Desktop tab)

## Problem

The GUI sometimes terminates with exit code `139` (SIGSEGV) while opening a task or switching to the Desktop tab. This appears correlated with QtWebEngine (`QWebEngineView`) navigation and/or GPU/fontconfig setup during Chromium initialization.

## Symptoms

- Exit code `139` (SIGSEGV) during task selection or Desktop tab interaction
- Chromium/QtWebEngine startup messages:
  - `GBM is not supported with the current configuration. Fallback to Vulkan rendering in Chromium.`
  - `Fontconfig error: Cannot load default config file: No such file: (null)`
- Crash triggers: selecting/opening tasks, clicking Desktop tab (noVNC embed), switching tabs

## Scope

1. Reproduce the crash consistently or rule out false correlation with Desktop tab
2. Narrow the crash to one or more of:
   - `QWebEngineView` initialization
   - `QWebEngineView.setUrl(...)` to noVNC URL
   - `QWebEngineView.setUrl("about:blank")` during hide/switch
   - GPU/Vulkan/GBM configuration
   - Fontconfig configuration/propagation
3. Propose concrete, minimal candidate fixes

## Investigation Resources

- Brainstorm notes: `.agents/temp/crash-exit-139/`
  - Summary: `summary-and-repro.md`
  - Code locations: `code-locations.md`
  - Hypotheses: `hypotheses.md`
  - Investigation steps: `investigation-steps.md`
  - Experiments: `experiments.md`
  - Acceptance criteria: `acceptance-criteria.md`
  - Mitigation idea: `out-of-process-mitigation.md`

## Acceptance Criteria

- A consistent repro path is documented (or the crash is ruled out as unrelated to the Desktop tab)
- The crash is narrowed to specific QtWebEngine/GPU/fontconfig initialization steps
- Concrete, minimal candidate fixes are proposed (implementation may be deferred to follow-up task)
