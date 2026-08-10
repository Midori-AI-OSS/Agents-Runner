# Expose GitHub Rate-Limit & Retry Settings in GitHub Config Pane

**Scope:** `agents_runner/ui/pages/settings_form.py`, `agents_runner/ui/_mixin_hints.py`  
**Dependencies:** #0091 (rate-limiter keys exist), #0093 (retry keys exist), #0097 (poll-interval widget + rate-warning label already present)  

## Outcome
Three existing runtime settings — `github_requests_per_second`, `github_pr_retry_interval_minutes`, and `github_pr_retry_max_minutes` — gain visible `QLineEdit` controls in the GitHub Config pane, auto-save and reload with existing settings wiring, and the existing rate-warning guidance updates to mention request pace.

## Background
The keys already exist across four layers with full validation but zero UI exposure:

| Key | Default | Valid Range | Set/Load | Validate | Consumed By |
|---|---|---|---|---|---|
| `github_requests_per_second` | `2` | `1`–`10` | `main_window.py:135`, `main_window_persistence.py:203` | `main_window_settings.py:402,405-410` | `rate_limiter.py:93,97` |
| `github_pr_retry_interval_minutes` | `5` | `0`–`60` | `main_window.py:133`, `main_window_persistence.py:201` | `main_window_settings.py:392-395` | `main_window_tasks_interactive_finalize.py:439,463` |
| `github_pr_retry_max_minutes` | `60` | `0`–`360` | `main_window.py:134`, `main_window_persistence.py:202` | `main_window_settings.py:397-400` | `main_window_tasks_interactive_finalize.py:440,464` |

## Acceptance Criteria

1. **Three new `QLineEdit` controls** added to the GitHub Config pane grid (`settings_form.py` lines 695–754), placed as rows 9–11 after the existing rate-warning label (row 8):
   - `_github_requests_per_second` — Label: `"Max requests per second"`, `QIntValidator(1, 10)`, placeholder `"2"`, `setMaximumWidth(120)`, tooltip: `"Maximum GitHub API requests per second across all environments. Lower values reduce rate-limit risk; higher values speed up polling and PR operations."`
   - `_github_pr_retry_interval_minutes` — Label: `"PR retry interval (min)"`, `QIntValidator(0, 60)`, placeholder `"5"`, `setMaximumWidth(120)`, tooltip: `"Minutes between retries when gh pr create is rate-limited after push. Set to 0 to disable rate-limit retry loop."`
   - `_github_pr_retry_max_minutes` — Label: `"PR retry max (min)"`, `QIntValidator(0, 360)`, placeholder `"60"`, `setMaximumWidth(120)`, tooltip: `"Maximum total minutes to keep retrying a rate-limited gh pr create before giving up. Has no effect when PR retry interval is 0."`

2. **Widget creation** in `_build_controls()` (near line 448, after `_github_poll_rate_warning_label` creation), following the existing `QLineEdit` + `QIntValidator` + `setMaximumWidth(120)` pattern used by `_github_poll_interval_s` (lines 441–447) and `_github_poll_startup_delay_s` (lines 434–440).

3. **Grid wiring** in `_build_pages()` github_config section (after row 8 / line 751), adding three `add_grid_row()` calls for rows 9, 10, 11 with appropriate labels and the new widgets. (The `github_config_body.addStretch(1)` on line 753 is already present.)

4. **Auto-load (`set_settings`)** — after line 1388, read each key with the same try/except + clamp pattern:
   ```python
   try:
       rps = max(1, min(10, int(settings.get("github_requests_per_second", 2))))
   except Exception:
       rps = 2
   self._github_requests_per_second.setText(str(rps))
   ```
   ...and analogous for the two retry keys with their respective ranges/defaults.

5. **Auto-save (`get_settings`)** — after line 1598, emit the keys with the same try/except + clamp read-back pattern, added to the returned dict as:
   ```python
   "github_requests_per_second": requests_per_second,
   "github_pr_retry_interval_minutes": pr_retry_interval,
   "github_pr_retry_max_minutes": pr_retry_max,
   ```

6. **Type hints** — in `agents_runner/ui/_mixin_hints.py` (~line 403, inside `SettingsPageHints`), add:
   ```python
   _github_requests_per_second: QLineEdit
   _github_pr_retry_interval_minutes: QLineEdit
   _github_pr_retry_max_minutes: QLineEdit
   ```

7. **Rate-warning guidance update** — the existing `_github_poll_rate_warning_label` tooltip (lines 452–455) already references "pace". Update it to explicitly mention requests-per-second alongside interval:
   - Tooltip: `"Each poll cycle sends multiple API requests per environment capped by the max requests-per-second setting. At this pace, the global account-wide rate limit (5,000 req/hr) could be exhausted. Increase the polling interval, reduce the max requests-per-second, or reduce polling-enabled environments to stay within safe limits."`

8. **Verification:**
   - Launch settings pane, confirm three new fields appear in GitHub Config below the rate-warning label.
   - Enter out-of-range values (e.g., `0`, `999`, `"abc"`) in each field, save, reopen — confirm values clamp to valid range on save and reload.
   - Confirm defaults (`2`, `5`, `60`) appear on first launch / when keys are missing from settings.
   - Set all three to non-default values, save, restart app — confirm values persist.
   - Set `github_pr_retry_interval_minutes` to `0` — confirm tooltip on `_github_pr_retry_max_minutes` still shows but the retry loop code path respects the disable (code unchanged).
   - Confirm rate-warning tooltip mentions "requests-per-second".
   - Run `uv run ruff format . && uv run ruff check . && uv run basedpyright` — all must pass.

## Implementation Notes
- Use `QLineEdit` + `QIntValidator` (not `QSpinBox`) for consistency with existing GitHub Config pane fields.
- No new config keys — only expose existing keys already loaded/validated/persisted.
- The settings page auto-saves via the existing `saved` → `_apply_settings` signal chain; the new widgets just need to connect to `_queue_debounced_autosave` via `textChanged` (follow the same pattern as `_github_poll_interval_s` — check `_connect_autosave_signals` or the `textChanged.connect` calls for the existing GitHub fields).
- Bump `TASK` version by `+1` in `pyproject.toml` upon completion.
