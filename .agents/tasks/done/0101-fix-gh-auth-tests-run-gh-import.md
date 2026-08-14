# 0101: Fix failing GitHub auth cache tests

## Status
- Created: 2026-08-14

## Summary
All 10 tests in `agents_runner/tests/test_gh_auth.py` fail with `AttributeError: module 'agents_runner.gh.auth' has no attribute 'run_gh'`. The tests monkeypatch `auth.run_gh`, but `run_gh` now lives in `agents_runner/gh/process.py` and `auth.py` resolves it via inline `from .process import run_gh` inside `_resolve_login_from_api` and `_refresh_snapshot`, so the module-level patch target no longer exists. Hoist the import to module level in `auth.py` (matching every sibling gh module and the repo rule against inline imports) so the tests pass unchanged.

## Scope
- **File:** `agents_runner/gh/auth.py` only; no test edits and no other production changes.
- **Out of scope:** basedpyright, unrelated refactors, and `.agents/tasks/not-ready/unify-runplan-pydantic-rescope.md` (do not touch).
- Lint is already clean on this branch: `uv run ruff check .` and `uv run ruff format --check .` both pass (verified 2026-08-14). No lint fixes are required.

## Acceptance Criteria
1. `auth.py` has a module-level `from .process import run_gh` import.
2. The two inline `from .process import run_gh` statements (currently lines 65 and 84) are removed.
3. All 10 previously failing tests in `agents_runner/tests/test_gh_auth.py` pass.
4. `.agents/scripts/test` exits with 0 failures.
5. `uv run ruff check .` and `uv run ruff format --check .` remain clean.

## Implementation Notes
- Baseline (verified 2026-08-14, branch `midoriaiagents/umber-173246cbe4`): 10 failed, 55 passed, 2 skipped; every failure is the same `AttributeError` at `monkeypatch.setattr(auth, "run_gh", ...)` in `test_gh_auth.py` (9 call sites, 10 tests because one is parametrized).
- Add `from .process import run_gh` after `from .errors import GhManagementError` (line 15).
- No circular import: `process.py` imports only `.errors` and `.rate_limiter`; `rate_limiter.py` has no gh-package imports.
- With the hoisted import, the two functions reference the module global, so `monkeypatch.setattr(auth, "run_gh", ...)` intercepts again.

## Verification Checklist
- [x] `uv sync --group ci && .agents/scripts/test` passes with 0 failures
- [x] `uv run ruff check .` clean
- [x] `uv run ruff format --check .` clean
- [x] `agents_runner/tests/test_gh_auth.py` unchanged

## Completion Note
- Completed: 2026-08-14. Hoisted `from .process import run_gh` to module level in `agents_runner/gh/auth.py` and removed the two inline imports in `_resolve_login_from_api` and `_refresh_snapshot`. Verified: 65 passed, 2 skipped, 0 failures; ruff check and format clean.
