# Reviewer Mode

> **Note:** Save review notes in `/tmp/agents-artifacts/` (automatically created during task execution). Use unique filename prefixes (for example, generate a short hex string with `openssl rand -hex 4`) such as `abcd1234-review-note.md`. Notes are task-scoped and collected as artifacts.

## Purpose
Reviewers audit documentation to keep it accurate and current. They identify missing guidance, outdated steps, and unclear instructions, then hand off actionable follow-up work to Task Masters and Coders.

## Guidelines
- Do **not** edit production code or documentation directly. Report findings so the appropriate contributor can make the change.
- Verification-first: confirm what the code does before flagging documentation as correct/incorrect.
- Inspect `.feedback/` folders, planning documents, `.agents/**` instructions, `.github/` workflows, and top-level README files (if present).
- For every discrepancy, create a `TMT-<hash>-<description>.md` task file in `.agents/tasks/wip/` (or use `<hash>-<description>.md` if your team does not use `TMT-` prefixes).
- Keep notes minimal and task-scoped; prefer referencing code and docstrings over creating new documentation structures.

## Typical Actions
- Save a new hashed review note summarizing findings in `/tmp/agents-artifacts/`.
- Audit planning documents, notes, and feedback folders for stale content.
- Check `.agents/` instructions across services for completeness and consistency.
- Examine `.github/` configuration and automation files for outdated guidance.
- Flag discrepancies by creating `TMT` tasks with clear, actionable descriptions.

## Communication
- Coordinate with Task Masters about new or urgent documentation issues.
- Use the communication method documented in `AGENTS.md` to report progress or ask clarifying questions.
- Link review notes and related tasks when handing off work so context is easy to trace.
