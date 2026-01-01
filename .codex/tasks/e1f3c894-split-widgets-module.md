# Split `codex_local_conatinerd/widgets.py` into a widgets package

## Context
`codex_local_conatinerd/widgets.py` is above the soft limit and contains multiple independent widget classes.

## Goal
Move each widget (or small related groups) into dedicated modules for maintainability and faster iteration.

## Proposed module layout
- `codex_local_conatinerd/widgets.py`: compatibility shim that re-exports symbols
- `codex_local_conatinerd/widgets/` package:
  - `glass_card.py`: `GlassCard`
  - `status_glyph.py`: `StatusGlyph`
  - `loading_bar.py`: `BouncingLoadingBar`
  - `log_highlighter.py`: `LogHighlighter`
  - `__init__.py`: re-exports used by the rest of the app

## Acceptance criteria
- Existing imports keep working (via re-exports).
- No widget module exceeds 600 lines; prefer ≤ 300.
- No visual/style changes other than those required to preserve behavior.

