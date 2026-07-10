# 001 — Scout the codebase and identify one real bug

Issue
- No known bug has been filed yet. We need to find one that is genuinely wrong in the current code.

Goal
- Dispatch a scout/explore agent to search the codebase for a real bug — not a style nit, not a missing feature, but something demonstrably broken (logic error, incorrect condition, wrong type usage, missing import, broken config path, etc.).
- The bug must be verifiable by reading source files; do not guess or fabricate.
- Scope: Focus on Python source files under `agents_runner/`. Skip SVG icon assets, markdown templates, and shell preflight scripts unless the bug is in their orchestration.

Strategy
1) Dispatch a `scout` sub-agent (or multiple) to audit key areas:
   - Main entry points (`main.py`, CLI routing)
   - Core subsystem packages under `agents_runner/`
   - Configuration loading, defaults, and config hygiene
   - Supervisor/orchestration layer
   - UI/theme/styling (Qt isolation)
   - Subprocess/Docker runners
   - Pydantic models and data flow
2) For each candidate bug, verify by reading the actual source files.
3) Select the most concrete, clearly reproducible bug.
4) Document: file path(s), line number(s), what is wrong, and what the correct behavior should be.

Completion
- A documented bug with file:line references and a short summary ready to be written up as a GitHub issue.
- Output goes to `/tmp/agents-artifacts/found-bug.md`.

Verify
- Re-read the implicated source lines to confirm the bug exists.
- The bug must be in current source (not outdated, not already fixed on main).
