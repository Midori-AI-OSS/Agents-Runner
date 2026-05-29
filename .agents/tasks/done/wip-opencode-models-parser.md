# Task: Create OpenCode models parser utility

**New file:** `agents_runner/opencode_models.py`

**Goal:** Create a non-UI utility module that parses `opencode models --verbose` subprocess output and returns structured data for populating model/variant dropdowns.

**Background:**
`opencode models --verbose` outputs each model as:
```
providerID/modelID
{JSON object with id, providerID, name, capabilities, variants, ...}
```
Models are separated by blank lines or by the next `providerID/modelID` header. The JSON includes a `variants` dict keyed by variant name with `reasoningEffort` values. Models from `opencode` provider need to be extracted.

**Steps:**
1. Create `agents_runner/opencode_models.py` (no Qt imports).
2. Add a function `parse_opencode_models() -> list[dict[str, object]]` that runs `opencode models --verbose` via `subprocess`, parses the output into a list of dicts, each containing at minimum: `id` (full `providerID/modelID` string), `name` (display name), `provider_id`, `variants` (list of variant names like `["low", "medium", "high", "max"]`).
3. Handle parsing errors gracefully: return empty list on failure, log via `midori_ai_logger`.
4. The parser should handle the alternating header/JSON format: collect lines until a blank line or next header, then parse accumulated JSON block.
5. Include a convenience function `opencode_model_options() -> list[tuple[str, str, list[str]]]` that returns a list of `(model_id, display_label, variant_names)` tuples, filtered to only opencode-provider models (providerID == "opencode"), sorted by name.

**Done criteria:**
- Module exists at `agents_runner/opencode_models.py`.
- `parse_opencode_models()` can be called independently and returns correct parsed data.
- `opencode_model_options()` returns a list suitable for populating a QComboBox.

## Completion

- 2026-05-29: Added `agents_runner/opencode_models.py` with `parse_opencode_models()` and `opencode_model_options()`, including subprocess error handling, logging, and verified parsing against live `opencode models --verbose` output.
