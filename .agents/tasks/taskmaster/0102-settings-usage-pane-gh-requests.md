# 0102: Add Settings Usage pane with GitHub CLI request totals and 60-minute line graph

## Status
- Created: 2026-08-17

## Summary
Add a generic Usage pane to the Settings page showing the app process's programmatic GitHub CLI (`gh`) request totals plus a rolling 60-minute per-minute line graph. Every programmatic `gh` process launch made by the app process counts, including internal auth/version checks and failed launches. Interactive terminal commands and `git` launches are excluded. Data is in-memory only (no persistence); the pane refreshes once per minute while the Settings page is visible; no explanatory copy.

## Scope
- New small, thread-safe, Qt-free counter module under `agents_runner/gh/` (e.g. `usage_counts.py`) exposing a record call and a snapshot (total + 60 one-minute buckets).
- Record at attempt time in `run_gh` (`agents_runner/gh/process.py`, line 22) when `args[0] == "gh"`, before `subprocess.run`, so non-zero exits, timeouts, and OSErrors all count.
- Record at the two raw `subprocess.run(["gh", ...])` call sites that bypass `run_gh`:
  - `agents_runner/gh/pr_validation.py` line 116 (`gh --version` internal version check)
  - `agents_runner/github_token.py` line 24 (`gh auth token` internal auth check)
- New Settings pane: register a `_SettingsPaneSpec` in `_default_pane_specs()` (`agents_runner/ui/pages/settings_form.py`, line 125) with `section="Usage"` so it appears under its own Usage navigation section (not the GitHub section) and build the page via `_build_pages()` (line 570). Pane body is only a total request count and a line graph of requests per minute for the trailing 60 minutes (custom QPainter widget, no new dependencies, no rounded corners). Keep `settings_form.py` additions minimal; place the pane widget in a small module (e.g. `agents_runner/ui/widgets/`).
- Refresh: 60 s QTimer on `SettingsPage` (`agents_runner/ui/pages/settings.py`), started in `showEvent`, stopped in `hideEvent` (mirror the existing polling start/stop pattern at lines 334-341).

## Out of scope
- `run_gh` calls with `args[0] != "gh"` (git binary via `git_ops.py`, `task_plan.py`, `repo_clone.py` line 126, `pr_validation.py` lines 70/89).
- `gh` commands executed inside Docker containers (`agents_runner/docker/agent_worker_github.py`): not app-process launches.
- Interactive terminal sessions (`terminal_apps.py`, `setup/orchestrator.py` new-session terminal launches, `setup/github_setup.py` commands such as `gh auth login`).
- `repo_clone.py` line 124 fabricated `CompletedProcess` (gh missing): no launch attempt, not counted.
- No persistence, no config keys, no new dependencies, no tests, no README/docs changes.
- No version bump now; the TASK bump applies only when the file moves `wip/` → `done/`.

## Acceptance Criteria
1. Every programmatic `gh` subprocess launch by the app process increments the in-memory total, including internal auth checks (`gh auth status`, `gh api user`, `gh auth token`) and version checks (`gh --version`), including failed launches (non-zero exit, timeout, OSError).
2. `git` launches and interactive terminal commands do not increment the counter.
3. The counter resets on app restart (no persistence).
4. Settings navigation shows a new Usage section containing the Usage pane with the total request count and a line graph of requests per minute for the trailing 60 minutes (60 one-minute buckets); the pane is not placed under the GitHub section.
5. While the Settings page is visible, the pane refreshes automatically once per minute; no refresh timer runs while hidden.
6. The pane contains no explanatory/descriptive copy; only the total and the chart (minimal data labels allowed).
7. `uv run ruff check .` and `uv run ruff format --check .` clean; `uv run basedpyright` passes.

## Implementation Notes
- Verified launch surface (branch `midoriaiagents/cerulean-ebbad0e7a9`): `run_gh` is the single gateway; gh calls pass `args[0] == "gh"` (`auth.py` lines 67/84, `work_items.py` lines 142/162, `repo_clone.py` line 122, `task_plan.py`, `pr_validation.py` line 144, `permissions.py` line 79). Two raw subprocess gh call sites bypass it: `pr_validation.py` line 116 and `github_token.py` line 24.
- `rate_limiter.py` already discriminates by `args[0]` (`acquire` skips git at line 195; `check_and_handle_rate_limit` handles only gh at line 298); follow the same discrimination.
- Recording at attempt time (before the subprocess call) guarantees failed launches count.
- `run_gh` runs on worker threads: guard the counter with a lock; a ring of 60 buckets indexed by `int(time.time()) // 60` suffices for the chart.
- UI rule: no `border-radius`/`addRoundedRect` in app widgets; keep the chart sharp/square.
- `_build_navigation()` (`settings_form.py`, line 889) renders one nav section label per unique `spec.section`, so a spec with `section="Usage"` (e.g. `key="usage"`, `title="Usage"`) creates the Usage section with no navigation code changes.

## Verification Checklist
- [ ] Launch app; open Settings → Usage (own navigation section, not under GitHub); total increments as gh-backed operations run
- [ ] A failed gh operation (non-zero exit, timeout, or missing binary) still counts
- [ ] Git-backed operations and interactive terminal usage do not count
- [ ] Chart shows per-minute buckets for the trailing 60 minutes and updates within 1 minute while Settings is visible
- [ ] Restart app; counter is zero again
- [ ] `uv run ruff check .`, `uv run ruff format --check .`, `uv run basedpyright` clean
