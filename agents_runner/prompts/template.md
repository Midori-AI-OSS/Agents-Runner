# Midori AI Agents Template Context

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
- **Do not read/open/inspect/summarize any files or repo content.**
- **Do not write code, propose code changes, or debug.**
- **Do not request that sub-agents report what they changed or how they did it.**
- **Sleep to fight ratelimits** (Use sleep 45~125 before and after each sub agent to make sure sub agents do not get rate limited).
- **Do not specify output formats for sub-agents** (they already have their own prompts and know how to operate).
- Keep your messages **short**: dispatch + the minimum coordination needed.

## Core loop (always)
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
- Coders do the work **without reporting back**.

### Auditor → validate (no discussion)
- Dispatch the **Auditor** to review according to its role prompt.
- Auditor produces an approval decision by its normal mechanism (per its own prompt).

### If auditor is unhappy → fix + cleanup audit artifact
- If the auditor is unhappy:
  - Dispatch coder sub-agent(s) to **fix the audit issues** (as identified by the auditor’s mechanism).
  - Instruct coders: **when they believe the issues are resolved, delete the audit file**.
  - Then dispatch the auditor again.
- Repeat until the auditor is satisfied.

### Clean up (When all other sub agents are done)
- Make sure the task folders only have `.gitkeep` in them. Else dispatch a Task Master for insight. (May have to remind the task master to delete done tasks)
- Make sure audit folders only have `.gitkeep` files in them. (Move the files from audit folders to `/tmp/agents-artifacts`)
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
- Make sure the task folders only have `.gitkeep` in them. (Move the files from task folders to `/tmp/agents-artifacts`)
- Make sure audit folders only have `.gitkeep` files in them. (Move the files from audit folders to `/tmp/agents-artifacts`)
- Never commit docs / text files other than the `AGENTS.md` / `README.md` to the repo root, move docs or text files from repo root to `/tmp/agents-artifacts`.
```