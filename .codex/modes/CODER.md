# Coder Mode

> **Note:** Keep technical documentation and implementation notes in `.codex/implementation/` for the area you are modifying. Capture process updates or workflow adjustments in `.codex/instructions/`.

## Purpose
Coders implement, refactor, and review code. The focus is on maintainable, well-tested changes that align with documented standards.

## Project-Specific Guidelines
- **Python 3.13+**: Use modern Python with type hints throughout
- **UI Styling**: Keep sharp/square corners—avoid `border-radius` in `codex_local_conatinerd/style.py` and `addRoundedRect(...)` in `codex_local_conatinerd/widgets.py`
- **Minimal diffs**: Avoid drive-by refactors; make surgical, focused changes
- **Test locally**: Run `uv run main.py` to verify UI changes before committing
- Write clear, well-structured code with meaningful naming and sufficient comments where intent is not obvious
- Commit frequently with descriptive messages summarizing the change and its purpose
- Keep documentation synchronized with code updates
- Break large changes into smaller commits or pull requests to simplify review
- Self-review your work for correctness, clarity, and completeness before submitting

## Typical Actions
- Implement features, bug fixes, or refactors referenced by `.codex/tasks/`.
- Update or create tests alongside code changes.
- Maintain supporting documentation in `.codex/implementation/`.
- Provide constructive feedback on peer contributions when requested.
- Capture follow-up ideas or improvements as new tasks rather than expanding scope mid-change.

## Communication
- Announce task start, handoff, and completion using the communication method defined in `AGENTS.md`.
- Reference related tasks, issues, or design docs in commit messages and pull requests.
- Surface blockers early so Task Masters or Managers can help resolve them.
