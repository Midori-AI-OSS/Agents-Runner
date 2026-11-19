# Reduce GitHub API Polling Overhead

Issue
- GitHub work polling refetches issue/PR threads for every open item every cycle (up to 120+ gh API calls per environment per 30s cycle, plus unbounded comment-history pagination walks).
- No persistence: auto-review seen/emit/pending state is in-memory and resets on restart, causing full re-fetch and possible re-emission.
- Multiple environments pointing at the same repository fetch lists independently.
- Suspected trigger of GitHub abuse detection / secondary rate limits for users.

Goal
- Add memory so items are recorded in a database once loaded, and items with no activity in N days (default 5) stop being re-pinged.
- Implement an inactivity filter (activity-based, via updated_at) with global settings and per-environment overrides.
- Implement persistent encrypted state (SQLite + Fernet key file, self-healing) for observed items, processed/reserved mentions, and pending eyes anchors.
- Deduplicate issue/PR list fetches across environments sharing a repository; keep per-environment auto-review evaluation and global emission dedup unchanged.
- Keep pending eyes anchors eligible for scanning regardless of the inactivity filter (consent semantics preserved).
- Defer incremental since= fetches and unchanged-parent skip to a later increment (see not-ready/gh-polling-incremental-fetch.md).

Completion
- Reference related GitHub issue(s) in commit messages and in the PR body where known.

Constraints
- Settings follow the normal app path: state.toml [settings] keys, normalization, defaults, settings UI + tooltips, per-env fields via environments model/serialize/wizard. No env-var config.
- Do not update README.md. Document via docstrings, tooltips, and the PR description.
- No GitHub tokens or issue/comment content stored in the state database. Fernet field-level encryption for state values; lookup keys plaintext (identifiers only).
- Self-healing key handling: missing key regenerates and quarantines the old database; corrupt database is quarantined and recreated; unwritable state dir degrades to in-memory mode. Never plaintext fallback.
- Thread scans remain per-environment; only pr/issue list fetches are deduplicated per repository.
- Minimal diffs; keep Qt imports under agents_runner/ui/.

Verify
- `uv sync --group ci`
- `uv run ruff format .`
- `uv run ruff check .`
- `uv run basedpyright`
- `.agents/scripts/test`

## Completion

- Settings added: `github_poll_inactive_filter_enabled` (default true), `github_poll_inactive_max_age_days` (default 5), per-env `github_poll_inactive_filter_mode` and `github_poll_inactive_max_age_days` (0 = inherit), wired through model/serialize/normalization/defaults/settings UI/environment form/wizard.
- New `agents_runner/gh/polling_state.py`: encrypted persistent SQLite state (Fernet key file, self-healing quarantine, cross-process init lock, memory fallback) with observation, reservation/ack/release, pending-anchor, and policy-fingerprint tables; unit tested.
- New `agents_runner/ui/pages/github_auto_review.py`: auto-review collection with activity-based inactivity filter (unparseable timestamps treated as active, pending anchors bypass), observation recording, and durable emission (reserve/ack/release) preserving the existing eyes-consent flow.
- `github_work_coordinator.py`: delegates auto-review collection; poll cycles fetch pr/issue lists once per repository and publish per environment; per-env auto-review and global emission dedup preserved.
- `work_items.py`: PR review-comment lists use sort=created&direction=desc and stop at the limit (endpoint-supported); issue comments and reviews pagination unchanged.
- Tests: `test_gh_polling_state.py` (13) and `test_github_work_coordinator_inactivity_filter.py` (18). Full suite green (102 passed, 1 skipped).
- Deferred to `not-ready/gh-polling-incremental-fetch.md`: since= incremental fetches and unchanged-parent skip (phase 2).

