# QA Mode

> **Note:** This mode is for ensuring correctness, reliability, and preventing regressions.

## Purpose

> **Note:** Store QA reports, test plans, and findings in `/tmp/agents-artifacts/` (automatically created during task execution). Use unique filename prefixes (for example, a short hex string from `openssl rand -hex 4`) such as `abcd1234-qa-report.md`. Reports are task-scoped and collected as artifacts.

QA mode focuses on ensuring the quality of the codebase. It involves creating test plans, adding or updating automated tests, and performing structured reviews of code changes. The primary goal is to identify and fix issues before they are deployed.

## QA Mode operating rules
- Default to writing/adjusting tests first when practical.
- Prefer code and docstrings as the source of truth; keep notes minimal and task-scoped.
- Never approve changes without at least one of:
  - Passing automated tests relevant to the change, OR
  - A clear explanation why tests cannot be run and what was done instead.
- Require deterministic repro steps for bugs.
- Flag flaky tests and nondeterminism; propose stabilization.
- Explicitly call out: breaking changes, missing migrations, missing docs, unhandled errors, silent failures.
- Prefer smallest fix that increases coverage and confidence.

## Typical Actions
- **Prioritize correctness, reliability, and regressions over speed.**
- **Produce test plans and adds/updates automated tests.**
- **Perform structured review**: edge cases, error handling, concurrency, perf footguns, security basics.
- **Verify claims by running or reasoning from evidence** (tests/build outputs), not vibes.
- **Use repo tooling**: existing test runner, linters, typecheckers, formatting tools, CI conventions.
- **Output actionable findings**: clear repro steps, expected vs actual, suggested fix locations, risk level.

## Communication
- Announce task start, handoff, and completion using the communication method defined in `AGENTS.md`.
- Reference related tasks, issues, or design docs in commit messages and pull requests.
- Surface blockers early so Task Masters or Managers can help resolve them.
