# .agents/tasks

Task workflow directories:

- `wip/`: active work items
- `done/`: completed/archived work items
- `taskmaster/`: Task Master queue and coordination

Rules:

- No files directly under `.agents/tasks/` except this `AGENTS.md`.
- Each subdirectory must include its own `AGENTS.md`.
- Task files are allowed only as `.md` or `.txt` directly inside `wip/`, `done/`, or `taskmaster/`.
- No deeper nesting under `.agents/tasks/`.
