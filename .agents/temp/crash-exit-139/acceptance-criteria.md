# Crash exit 139 — acceptance criteria (brainstorm)

- A consistent repro path is documented (or the crash is ruled out as unrelated to the Desktop tab).
- The crash is narrowed to one or more of:
  - `QWebEngineView` initialization
  - `QWebEngineView.setUrl(...)` to noVNC URL
  - `QWebEngineView.setUrl("about:blank")` during hide/switch
  - GPU/Vulkan/GBM configuration
  - Fontconfig configuration/propagation
- Concrete, minimal candidate fixes are proposed (but not implemented in this brainstorm set).
