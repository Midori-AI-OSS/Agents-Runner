# Widgets Split

- Custom Qt widgets live under `codex_local_conatinerd/widgets/` with a re-exporting `__init__.py`.
- Widget names/import paths remain stable for callers via the package exports.
- The square-corner constraint remains enforced (no rounded painting helpers introduced).

