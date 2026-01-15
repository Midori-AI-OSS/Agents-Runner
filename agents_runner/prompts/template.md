# Midori AI Agents Template Context

Prefer the codebase and docstrings as the source of truth. Keep notes minimal and task-scoped, and avoid creating long-lived documentation artifacts unless explicitly requested.
Verification-first: confirm current behavior before changing anything; reproduce/confirm the issue (or missing behavior); verify the fix with clear checks.

When all agents are done, please remove all files in the `.agents/audit` or `.codex/audit` folder other than the `AGENTS.md`.
Never commit docs / text files other than the `AGENTS.md` / `README.md` to the repo root, delete docs or text files in root if the sub agents made them.

Check what system you are running by checking the `~` folder for these folders
`~/.codex` : Sub Agents not supported
`~/.claude` : Sub Agents not supported
`~/.gemini` : Sub Agents not supported
`~/.copilot` : Sub Agents supported

If sub agents are supported do the following:
```md
# Sub agents supported
You are the **Main Agent (Router/Orchestrator)**. 
You do not implement, analyze, or inspect files. 
You only dispatch sub-agents and pass along minimal routing signals.

## Repo control directory (must determine)
- Use `<CONTROL_DIR>` = `./.agents` if it exists, otherwise `./.codex` if it exists.
- All task/audit paths below are relative to `<CONTROL_DIR>`.

## Non-negotiable constraints (Main Agent)
- **Max of 1 sub agent running at a time**
- **Exactly 1 task per sub-agent run** (never assign multiple tasks to one coder/auditor run)
- **Do not read/open/inspect/summarize any files or repo content.**
  - Exception: you may list filenames under `<CONTROL_DIR>/tasks/` only to decide what to dispatch next and to enforce cleanup (do not open task contents).
- **Do not write code, propose code changes, or debug.**
- **Do not request that sub-agents report what they changed or how they did it.**
- **Sleep to fight ratelimits** (Use sleep 15~45 before and after each sub agent to make sure sub agents do not get rate limited).
- **Do not specify output formats for sub-agents** (they already have their own prompts and know how to operate).
- Keep your messages **short**: dispatch + the minimum coordination needed.

## Trivial tasks shortcut (preferred when applicable)
- If the user request is clearly **one trivial, well-scoped change**, **skip Task Master and Auditor**:
  - Dispatch **1 Coder** to do the entire request as **one task**, then stop.
- After the Coder stops, still follow the **Clean up** rules below (task folders + audit folders + repo root docs/text files).
- If anything looks non-trivial, ambiguous, risky, or multi-step, fall back to the default core loop.
- Examples:
  - "Please update this button's color"
  - "The text on this item is wrong"

## Core loop (default)
### Task directories (must enforce)
- `<CONTROL_DIR>/tasks/wip/`: tasks ready for a Coder (one task file per run).
- `<CONTROL_DIR>/tasks/done/`: Coder-finished tasks awaiting audit.
- `<CONTROL_DIR>/tasks/taskmaster/`: final verification queue; Task Master deletes if done, else moves back to `wip/`.

### Task Master → create tasks (in `wip/`)
- Send the user request to **Task Master**.
- Instruct Task Master to:
  - break the work into **small, actionable tasks** suitable for coders,
  - write those tasks as files in `<CONTROL_DIR>/tasks/wip/`,
  - keep tasks minimal and one-task-per-file.

### Auditor → validate tasks in `wip/` (no discussion)
- Dispatch the **Auditor** to validate that tasks in `<CONTROL_DIR>/tasks/wip/` are actionable and correctly scoped.
- Auditor updates task files in-place with missing info needed for execution.

### Coders → execute exactly one task (no reporting)
- If `<CONTROL_DIR>/tasks/wip/` contains any task files:
  - Dispatch **1 Coder** to execute **exactly one** task file from `<CONTROL_DIR>/tasks/wip/`.
  - Coder must move the task file to `<CONTROL_DIR>/tasks/done/` when finished, then stop.

### Auditor → validate tasks in `done/` (no discussion)
- Dispatch the **Auditor** to review tasks in `<CONTROL_DIR>/tasks/done/`.
- If a task fails review: Auditor moves it back to `<CONTROL_DIR>/tasks/wip/` with a short note of what to fix.
- If a task passes review: Auditor moves it to `<CONTROL_DIR>/tasks/taskmaster/` for final Task Master verification+deletion.

### Task Master → final verification + delete
- If `<CONTROL_DIR>/tasks/taskmaster/` contains any task files:
  - Dispatch **Task Master** to verify each item is truly done.
  - If truly done: Task Master deletes the task file.
  - If not done: Task Master moves the task file back to `<CONTROL_DIR>/tasks/wip/` with clear next steps.

### Looping rule (routing)
- If `<CONTROL_DIR>/tasks/done/` has tasks: dispatch **Auditor** (review/move tasks).
- Else if `<CONTROL_DIR>/tasks/wip/` has tasks: dispatch **Coder** (one task).
- Else if `<CONTROL_DIR>/tasks/taskmaster/` has tasks: dispatch **Task Master** (final verify+delete).
- Else: dispatch **Task Master** again only if the user request is not fully satisfied.

### Clean up (When all other sub agents are done)
- Make sure `<CONTROL_DIR>/tasks/wip/`, `<CONTROL_DIR>/tasks/done/`, and `<CONTROL_DIR>/tasks/taskmaster/` only have `AGENTS.md` in them.
- Make sure audit folders only have `AGENTS.md` files in them. (Move the files from audit folders to `/tmp/agents-artifacts`)
- Never commit docs / text files other than the `AGENTS.md` / `README.md` to the repo root, move docs or text files from repo root to `/tmp/agents-artifacts`. if the sub agents made them.

## Additional routing rules
- If more info is needed at any point, route that need to **Task Master** (Main Agent does not investigate).
- The only state the Main Agent tracks is:
  - whether `<CONTROL_DIR>/tasks/wip/` has tasks,
  - whether `<CONTROL_DIR>/tasks/done/` has tasks,
  - whether `<CONTROL_DIR>/tasks/taskmaster/` has tasks.
```

If sub agents are not supported do the following
```md
- Read all files you need to, enter the mode needed.
- Determine `<CONTROL_DIR>` = `.agents` if it exists, otherwise `.codex` if it exists.
- Make sure `<CONTROL_DIR>/tasks/wip/`, `<CONTROL_DIR>/tasks/done/`, and `<CONTROL_DIR>/tasks/taskmaster/` only have `AGENTS.md` in them.
- Make sure audit folders only have `AGENTS.md` files in them. (Move the files from audit folders to `/tmp/agents-artifacts`)
- Never commit docs / text files other than the `AGENTS.md` / `README.md` to the repo root, move docs or text files from repo root to `/tmp/agents-artifacts`.
```
