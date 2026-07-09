# Task: Fix pyright errors in agents_runner/ui/dialogs/agent_config_dialog.py

## File
File: `agents_runner/ui/dialogs/agent_config_dialog.py`
Lines: 199

## Category
`agent-config-root`

## Errors
```
  Line 199: Cannot access attribute "_root" for class "AgentConfigDialog*"
```

## Fix
`AgentConfigDialog` extends `ThemedDialog` (not a mixin). `ThemedDialog.__init__` sets `self._background_root = GlassRoot(self)` (line 81), but never `self._root`.
Line 199 calls `self._root.set_theme_name(...)` which fails because `_root` is not defined.
Either:
(a) Add `self._root = self._background_root` in `AgentConfigDialog.__init__` after `super().__init__()`.
(b) Change line 199 to use `self._background_root.set_theme_name(...)` directly.

## Verification
```bash
uv run pyright agents_runner/ui/dialogs/agent_config_dialog.py
```
