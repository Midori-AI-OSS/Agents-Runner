# 0099: Convert Five GitHub Polling/Rate/Retry Fields to QSpinBox

Convert the five GitHub polling/rate/retry numeric fields in `agents_runner/ui/pages/settings_form.py` from QLineEdit/QIntValidator to QSpinBox controls matching the Storage panel pattern (spelled-out suffixes, clean labels, direct value access).

## Fields

| # | Widget | Range | Default | Suffix |
|---|--------|-------|---------|--------|
| 1 | `_github_poll_startup_delay_s` | 0–3600 | 35 | ` seconds` |
| 2 | `_github_poll_interval_s` | 5–3600 | 30 | ` seconds` |
| 3 | `_github_requests_per_second` | 1–10 | 2 | ` per second` |
| 4 | `_github_pr_retry_interval_minutes` | 0–60 | 5 | ` minutes` |
| 5 | `_github_pr_retry_max_minutes` | 0–360 | 60 | ` minutes` |

Tooltips, persisted keys (`github_poll_startup_delay_s`, `github_poll_interval_s`, `github_requests_per_second`, `github_pr_retry_interval_minutes`, `github_pr_retry_max_minutes`), and runtime behavior (int values in settings dict) are unchanged.

## Changes

### 1. `agents_runner/ui/pages/settings_form.py`

**A. Widget creation** (lines 434–480): Replace each `QLineEdit()` + `setValidator(QIntValidator(...))` + `setPlaceholderText(...)` + `setMaximumWidth(120)` block with `QSpinBox()` + `setRange(min, max)` + `setSuffix("...")` + `setValue(default)`. Keep tooltips verbatim.

**B. Grid labels** (lines 761, 767, 779, 785, 791): Remove unit suffixes from QLabel text since QSpinBox suffix now handles them:
- `"Polling interval (s)"` → `"Polling interval"`
- `"Polling startup delay (s)"` → `"Polling startup delay"`
- `"Max requests per second"` → `"Max requests"`
- `"PR retry interval (min)"` → `"PR retry interval"`
- `"PR retry max (min)"` → `"PR retry max"`

**C. Load** (`set_settings`, lines 1421–1445): Replace each tight `try/except + setText(str(clamped))` block with `_clamp_spin_value` + `setValue(...)` (same pattern as Storage cleanup fields at lines 1474–1500).

**D. Save** (`get_settings`, lines 1623–1648): Replace each `.text()` parsing + try/except + clamp block with `.value()` direct access (same pattern as Storage cleanup fields at lines 1684–1687).

**E. Warning reader** (`_refresh_github_poll_rate_warning`, line 1960): Replace `str(self._github_poll_interval_s.text() or "30").strip()` with `self._github_poll_interval_s.value()`.

**F. Imports:** Remove `QIntValidator` from line 11 import and `QLineEdit` from line 19 import (both unused after conversion).

### 2. `agents_runner/ui/pages/settings.py`

**Signal connections** (lines 192–197): Change `.textChanged` to `.valueChanged` for all five GitHub fields. Line 194: change `self._github_poll_interval_s.textChanged.connect(self._refresh_github_poll_rate_warning)` to use `valueChanged`.

### 3. `agents_runner/ui/_mixin_hints.py`

**Type hints** (lines 400, 403–406): Change `QLineEdit` to `QSpinBox` for all five fields.

## Acceptance Criteria

1. All five fields render as QSpinBox with correct range, suffix, and default value.
2. Loading an existing config clamps out-of-range persisted values via `_clamp_spin_value` (same behavior as today's clamping logic).
3. Saving retrieves `.value()` directly with no string parsing (simpler, more reliable).
4. Warning label continues to react to interval changes and polling checkbox toggle.
5. Grid row labels no longer include redundant unit suffixes.
6. Autosave fires on value changes (not text changes).
7. `_mixin_hints.py` type hints updated.
8. Persisted config keys unchanged; consumers of the settings dict (`github_work_coordinator.py`, `task_plan.py`) unaffected.
9. Zero new ruff or basedpyright errors; QIntValidator and QLineEdit imports cleaned up.

## Verification Checklist

- [ ] `ruff format .` — clean
- [ ] `ruff check .` — clean
- [ ] `basedpyright` — zero new errors in modified files
- [ ] Load config with out-of-range values → clamped on display
- [ ] Change a spinbox value → autosave fires
- [ ] Change polling interval → warning label updates
- [ ] Toggle polling checkbox → warning label updates
- [ ] Save settings → all five keys persisted as ints in TOML
- [ ] `QIntValidator` and `QLineEdit` imports no longer present in settings_form.py
