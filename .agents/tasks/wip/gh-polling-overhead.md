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
