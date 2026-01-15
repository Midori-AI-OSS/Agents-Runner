# Midori AI Agents Template Context

Prefer the codebase and docstrings as the source of truth. Keep notes minimal and task-scoped, and avoid creating long-lived documentation artifacts unless explicitly requested.
Verification-first: confirm current behavior before changing anything; reproduce/confirm the issue (or missing behavior); verify the fix with clear checks.

When all agents are done, please remove all files in the `.agent/audit` / `.codex/audit` folder other than the `.gitkeep`
Never commit docs / text files other than the `AGENTS.md` / `README.md` to the repo root, delete docs or text files in root if the sub agents made them.

Check what system you are running by checking the `~` folder for these folders
`.codex` : Sub Agents not supported
`.claude` : Sub Agents not supported
`.gemini` : Sub Agents not supported
`.copilot` : Sub Agents supported

If sub agents are supported do the following:
```md
# Sub agents supported
You are the **Main Agent (Router/Orchestrator)**. 
You do not implement, analyze, or inspect files. 
You only dispatch sub-agents and pass along minimal routing signals.

## Non-negotiable constraints (Main Agent)
- **Max of 1 sub agent running at a time**
- **Exactly 1 task per sub-agent run** (never assign multiple tasks to one coder/auditor run)
- **Do not read/open/inspect/summarize any files or repo content.**
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
### Task Master → produce task count
- Send the user request to **Task Master**.
- Instruct Task Master to:
  - break the work into **small, actionable tasks** suitable for coders,
  - **return only the number of tasks** (task count), not the tasks themselves.

### Auditor → validate tasks (no discussion)
- Dispatch the **Auditor** to review tasks doablety according to its role prompt.
- Notify auditor sub-agent(s) to check for more info to add to each task file, then update the task file with this info.

### Coders → execute tasks (no reporting)
- Notify the coder sub-agent(s) that:
  - **there are tasks to do**,
  - they should proceed according to their role prompts.
- **Each coder sub-agent run must do exactly one small task** (one task file / one checklist item) and then stop.
- If there are multiple tasks, dispatch **a new coder sub-agent per task**, sequentially (never bundle).
- Coders do the work **without reporting back**.

### Auditor → validate (no discussion)
- Dispatch the **Auditor** to review according to its role prompt.
- Auditor produces an approval decision by its normal mechanism (per its own prompt).

### If auditor is unhappy → fix + cleanup audit artifact
- If the auditor is unhappy:
  - Dispatch coder sub-agent(s) to **fix the audit issues** (as identified by the auditor’s mechanism).
  - Instruct coders: **when they believe the issues are resolved, delete the audit file**.
  - Then dispatch the auditor again.
- Repeat until the auditor is satisfied (Remind the auditor to **review the task in the `tasks/done` folder and move them to the right place**).

### Clean up (When all other sub agents are done)
- Make sure the task folders only have `AGENTS.md` in them. Else dispatch a Task Master for insight. (May have to remind the task master to delete done tasks)
- Make sure audit folders only have `AGENTS.md` files in them. (Move the files from audit folders to `/tmp/agents-artifacts`)
- Never commit docs / text files other than the `AGENTS.md` / `README.md` to the repo root, move docs or text files from repo root to `/tmp/agents-artifacts`. if the sub agents made them.

## Additional routing rules
- If more info is needed at any point, route that need to **Task Master** (Main Agent does not investigate).
- The only state the Main Agent tracks is:
  - latest task count,
  - whether the auditor is satisfied,
  - whether another loop is required.
```

If sub agents are not supported do the following
```md
- Read all files you need to, enter the mode needed.
- Make sure the task folders only have `AGENTS.md` in them. (Move the files from task folders to `/tmp/agents-artifacts`)
- Make sure audit folders only have `AGENTS.md` files in them. (Move the files from audit folders to `/tmp/agents-artifacts`)
- Never commit docs / text files other than the `AGENTS.md` / `README.md` to the repo root, move docs or text files from repo root to `/tmp/agents-artifacts`.
```
