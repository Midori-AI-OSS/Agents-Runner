# Split `codex_local_conatinerd/style.py` into palette + stylesheet builder

## Context
`codex_local_conatinerd/style.py` is above the soft limit and will likely grow as UI evolves.

## Goal
Separate style constants (palette/metrics) from stylesheet construction to keep modules small and reusable.

## Proposed module layout
- `codex_local_conatinerd/style.py`: compatibility shim exporting `app_stylesheet()`
- `codex_local_conatinerd/style/` package:
  - `palette.py`: colors and constants
  - `metrics.py`: spacing/font sizes (if applicable)
  - `sheet.py`: stylesheet builder functions
  - `__init__.py`: exports `app_stylesheet`

## Acceptance criteria
- `app_stylesheet()` output remains byte-for-byte identical (or visually identical if ordering is not stable).
- No file exceeds 600 lines; prefer ≤ 300.
- Square-corner constraint remains enforced (no `border-radius`, no rounded painting).

