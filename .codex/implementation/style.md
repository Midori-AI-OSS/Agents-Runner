# UI Stylesheet Architecture

The app stylesheet is built by `codex_local_conatinerd/style/sheet.py:app_stylesheet`.

## Layout

- `codex_local_conatinerd/style/__init__.py`: public re-export (`app_stylesheet`)
- `codex_local_conatinerd/style/palette.py`: color tokens used by the stylesheet builder
- `codex_local_conatinerd/style/metrics.py`: font/spacing tokens used by the stylesheet builder
- `codex_local_conatinerd/style/template_base.py`: base widget QSS template
- `codex_local_conatinerd/style/template_tasks.py`: task list/row QSS template

## Notes

- `codex_local_conatinerd.style` is now a package (not a single `style.py` module) so the public import path stays stable: `from codex_local_conatinerd.style import app_stylesheet`.
- `app_stylesheet()` output is intended to remain byte-for-byte stable; current reference hash is `sha256=1bb29a7ba6486d9fbb1a00113f66b372ca31400b25f47807f3d143998aa8641e`.
- Keep square corners: avoid `border-radius` values other than `0px` (and avoid any rounded custom painting).

