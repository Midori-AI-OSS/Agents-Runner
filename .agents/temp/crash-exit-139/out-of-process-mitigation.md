# Crash exit 139 — mitigation idea: out-of-process viewer (brainstorm)

For isolation from native crashes, run the Desktop (noVNC) viewer in a separate helper process instead of embedding `QWebEngineView` in the main UI.

- Tracking task: `.agents/tasks/wip/qtwebengine-desktop-viewer-out-of-process.md`
