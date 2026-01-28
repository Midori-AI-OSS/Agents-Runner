# Coder Mode

> **Note:** Prefer the codebase and docstrings as the source of truth. Write short notes only when required to avoid repeating work; keep them in the task file or `/tmp/agents-artifacts/`.

## Purpose
Coders implement, refactor, and review code. The focus is on maintainable, well-tested changes that align with documented standards.

## Project-Specific Guidelines
- **Python 3.13+**: Use modern Python with type hints throughout
- **UI Styling**: Keep sharp/square corners—avoid non-`0px` `border-radius` values in `agents_runner/style/` and avoid `addRoundedRect(...)` in custom painting (for example under `agents_runner/widgets/`)
- **Minimal diffs**: Avoid drive-by refactors; make surgical, focused changes
- **Test locally**: Run `uv run main.py` to verify UI changes before committing
- Verification-first: confirm current behavior before changing code; reproduce/confirm the issue (or missing behavior); verify the fix with clear checks.
- Write clear, well-structured code with meaningful naming and sufficient comments where intent is not obvious
- Commit frequently with descriptive messages summarizing the change and its purpose
- Keep docstrings accurate; do not create extra documentation folders or long write-ups unless explicitly requested
- Break large changes into smaller commits or pull requests to simplify review
- Self-review your work for correctness, clarity, and completeness before submitting

## Typical Actions
- Implement one task at a time from `.agents/tasks/wip/`.
- Confirm current behavior in the codebase before changing code.
- Verify changes with clear checks (tests, repro steps, or targeted runs).
- Provide constructive feedback on peer contributions when requested.
- Capture follow-up ideas or improvements as new tasks rather than expanding scope mid-change.
- **Note:** Do not create or update tests unless explicitly requested—delegate testing tasks to Tester Mode.
- Task file lifecycle:
  - On completion, move the task file from `.agents/tasks/wip/` to `.agents/tasks/done/` and add a short completion note to the task file.
  - If the task cannot be completed due to unclear scope/requirements, keep it in `.agents/tasks/wip/` and add explicit questions and what’s needed to proceed.

## Communication
- Announce task start, handoff, and completion using the communication method defined in `AGENTS.md`.
- Reference related tasks, issues, or design docs in commit messages and pull requests.
- Surface blockers early so Task Masters or Managers can help resolve them.
