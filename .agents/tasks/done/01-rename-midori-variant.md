Rename agents_runner/ui/themes/midori_variant.py file and all internal identifiers.

1. Rename file midori_variant.py -> midoriai_variant.py.
2. Rename class MidoriVariantSpec -> MidoriaiVariantSpec (every occurrence).
3. Rename class _MidoriRuntime -> _MidoriaiRuntime (every occurrence).
4. Rename class _MidoriVariantBackground -> _MidoriaiVariantBackground (every occurrence).
5. Rename function create_midori_background -> create_midoriai_background (every occurrence).
6. Fix docstrings: replace standalone "Midori" (not part of "Midori AI") with "Midori AI" where referring to the organization/product. Lines affected: line 23 docstring ("Midori theme" -> "Midori AI theme"), line 305 docstring ("Midori variant" -> "Midori AI variant"). Line 1 already uses "Midori AI" — leave it.

---

**Completed:** File renamed to `midoriai_variant.py`. All classes (`MidoriaiVariantSpec`, `_MidoriaiRuntime`, `_MidoriaiVariantBackground`) and function (`create_midoriai_background`) renamed. Docstrings updated. No import sites changed (separate task `02-update-theme-imports`).
