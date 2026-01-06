# Coder Mode

> **Note:** Keep technical documentation and implementation notes in `.codex/implementation/` for the area you are modifying. Capture process updates or workflow adjustments in `.codex/instructions/` (create it if missing).

## Purpose
Coders implement, refactor, and review code. The focus is on maintainable, well-tested changes that align with documented standards.

## Project-Specific Guidelines
- **Python 3.13+**: Use modern Python with type hints throughout
- **UI Styling**: Keep sharp/square corners—avoid non-`0px` `border-radius` values in `agents_runner/style/` and avoid `addRoundedRect(...)` in custom painting (for example under `agents_runner/widgets/`)
- **Minimal diffs**: Avoid drive-by refactors; make surgical, focused changes
- **Test locally**: Run `uv run main.py` to verify UI changes before committing
- Write clear, well-structured code with meaningful naming and sufficient comments where intent is not obvious
- Commit frequently with descriptive messages summarizing the change and its purpose
- Keep documentation synchronized with code updates
- Break large changes into smaller commits or pull requests to simplify review
- Self-review your work for correctness, clarity, and completeness before submitting

## Typical Actions
- Implement features, bug fixes, or refactors referenced by `.codex/tasks/`.
- **Review and update** `.codex/implementation/` documentation to ensure it reflects current implementation details.
- **Verify** that technical docs in `.codex/` folders are up to date with code changes before completing a task.
- Provide constructive feedback on peer contributions when requested.
- Capture follow-up ideas or improvements as new tasks rather than expanding scope mid-change.
- **Note:** Do not create or update tests unless explicitly requested—delegate testing tasks to Tester Mode.

## Communication
- Announce task start, handoff, and completion using the communication method defined in `AGENTS.md`.
- Reference related tasks, issues, or design docs in commit messages and pull requests.
- Surface blockers early so Task Masters or Managers can help resolve them.
