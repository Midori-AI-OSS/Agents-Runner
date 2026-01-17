# Task — Replace OS/theme icons with vendored Lucide SVG icons (HiDPI crisp)

## 1. Title (short)
Vendored Lucide icons + HiDPI rendering

## 2. Summary (1–3 sentences)
Stop using OS/theme-provided icons (`self.style().standardIcon(...)`) so the UI looks consistent across platforms. Vendor a small Lucide SVG subset into the repo and add a cached HiDPI-aware SVG→`QIcon` renderer so icons are crisp and theme-tinted.

## 3. Implementation notes (key decisions + constraints)
- No runtime downloads; vendor SVGs in-repo.
- Bulk import is allowed as a contributor/dev step (network during development is OK), but the shipped app must never fetch icons at runtime.
- Use Lucide SVGs (stroke-based, `stroke="currentColor"`). Tint by replacing `currentColor` with the desired hex (or set stroke via a minimal SVG edit).
- Render via `PySide6.QtSvg.QSvgRenderer` into a `QPixmap` sized at `size * devicePixelRatio`, then set `pixmap.setDevicePixelRatio(dpr)` to avoid blur.
- Ensure widgets don’t rescale icons:
  - Always call `button.setIconSize(QSize(size, size))` when setting the icon.
- Cache icons by `(name, size, color_rgba, dpr)` to avoid repeated SVG rendering.
- Keep UI sharp (no rounded corners). Keep diffs minimal.

## 3.1 Bulk icon import (start with ~800)
- Goal: vendor a large baseline set so future UI work rarely needs new icon fetches.
- Prefer a one-time vendor workflow over per-file HTTP downloads:
  - Use git sparse-checkout (or a temporary full clone) of `lucide-icons/lucide`, then copy `icons/*.svg` into `agents_runner/assets/icons/lucide/`.
  - Keep the imported set to ~800 icons initially to limit repo bloat.
  - Selection must be “most likely needed” rather than alphabetical:
    1) Include all icons that the app currently needs (derive by mapping existing `standardIcon(...)` usages + any explicit icon usages to Lucide names).
    2) Include a curated “common UI” set (navigation, CRUD, media controls, status, alerts, links, clipboard, search, settings, etc.).
    3) Fill remaining slots up to ~800 from the rest (any deterministic method is fine once (1) and (2) are satisfied).
  - Do not add a submodule; this is a one-time vendor into this repo.
- Validation checks (required):
  - No `.svg` files are 0 bytes.
  - Each downloaded file contains an `<svg` tag (guard against HTML error pages).
  - Script prints a summary: requested count, downloaded count, skipped existing count, failures list.
  - If any download fails or results in invalid/empty SVG, treat it as an error and retry once (then fail with a clear list).
- Keep the directory clean:
  - Only `.svg` files, lowercase names, match upstream filenames.
  - Consider adding a small allowlist/denylist if any upstream files are non-standard.

## 4. Suggested repo layout
- Add directory: `agents_runner/assets/icons/lucide/`
  - Example files to vendor first: `copy.svg`, `external-link.svg`, `refresh-cw.svg`, `search.svg`, `settings.svg`, `play.svg`, `pause.svg`, `stop-circle.svg`, `trash-2.svg`, `check.svg`, `x.svg`, `info.svg`, `alert-circle.svg`, `github.svg`, `arrow-left.svg`, `arrow-right.svg`.
- Add helper module: `agents_runner/ui/lucide_icons.py`
  - Public API: `lucide_icon(name: str, *, size: int = 16, color: QColor | None = None) -> QIcon`

## 5. Replacement scope (initial pass)
- Replace `self.style().standardIcon(...)` usages in the UI with `lucide_icon(...)` for consistency.
  - Examples to update (search with ripgrep): `standardIcon(` across `agents_runner/ui/`.
- Keep the existing app icon (`agents_runner/midoriai-logo.png`).

## 6. Acceptance criteria (clear, testable statements)
- App no longer depends on OS/theme icons for core UI buttons (no `standardIcon` usage in `agents_runner/ui/`, or it is reduced to explicitly allowed cases).
- Icons render crisp (no blur) on HiDPI displays.
- Icons tint correctly to the app theme color (e.g., `rgba(237,239,245,...)`).
- No network access is required at runtime (SVGs are vendored).
- At least ~800 Lucide SVG files are present under `agents_runner/assets/icons/lucide/`, and none are 0 bytes.
- Bulk import script reports and fails loudly on any invalid/empty downloads.

## 7. Expected files to modify (explicit paths)
- Add SVGs under `agents_runner/assets/icons/lucide/`
- Add `agents_runner/ui/lucide_icons.py`
- Update various files under `agents_runner/ui/` that currently call `standardIcon(...)`

## 8. Out of scope (what not to do)
- Do not add a runtime icon downloader.
- Do not change unrelated UI layouts beyond swapping icon sources.
- Do not update `README.md` or add tests.
