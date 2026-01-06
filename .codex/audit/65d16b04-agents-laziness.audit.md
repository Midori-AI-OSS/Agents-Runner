# Repo Audit: "Agents are being lazy"

- Date: 2026-01-06
- Scope: `AGENTS.md`, `.codex/modes/*.md`, selected `.codex/implementation/*.md`, repo `.codex/*` structure

## What I reviewed
- `AGENTS.md`
- Mode guides:
  - `.codex/modes/AUDITOR.md`
  - `.codex/modes/MANAGER.md`
  - `.codex/modes/TASKMASTER.md`
  - `.codex/modes/REVIEWER.md`
  - `.codex/modes/CODER.md`
- Implementation notes (spot-check for consistency):
  - `.codex/implementation/environments.md`
  - `.codex/implementation/style.md`

## Repo state observations
- `.codex/audit/` exists and already contains `.gitkeep`.
- `.codex/tasks/` has no active tasks (only `.codex/tasks/done/.gitkeep`).
- `.codex/reviews/` and `.codex/instructions/` are empty aside from `.gitkeep`.
- No `.codex/requests/` directory found.

## Likely causes of “lazy” agent behavior
1. **Most modes are written to “not do the work.”**
   - `TASKMASTER.md`: explicitly says Task Masters *never implement features or edit production code directly*.
   - `REVIEWER.md`: says reviewers *do not edit production code or documentation directly* (this is unusually strict for a “Reviewer” role and can lead to “I can’t do that” behavior).
   - `MANAGER.md`: says managers don’t implement unless following another mode.
   - Net effect: if your runner defaults to a non-CODER mode (or the agent self-selects it), the agent is incentivized to “handoff” rather than act.

2. **No active task inventory means agents have no “permission structure” to execute.**
   Your process docs repeatedly reference work flowing through `.codex/tasks/`. With an empty task queue, a cautious agent may (reasonably) stall: “I’m not supposed to do work unless it’s in a task.”

3. **Stale/incorrect path references reduce confidence and increase refusal rate.**
   Several docs referenced stale paths from a prior folder layout; this repo uses `agents_runner/...`.
   - Example: `.codex/implementation/style.md` and `.codex/implementation/environments.md` referenced the old layout.
   - Example: `.codex/modes/CODER.md` referenced the old layout paths.
   When instructions don’t match the repo, agents tend to:
   - stop early to avoid damaging the codebase,
   - ask for clarification repeatedly,
   - or do “safe” read-only work (which can look like laziness).

4. **AGENTS.md encourages conservative execution by default.**
   `AGENTS.md` includes guidance like “Do not update the readme unless asked” and “Do not build tests unless asked.” That’s fine, but if the agent already lacks a concrete task, these constraints compound into “I shouldn’t do much.”

## “Put yourself in their place” (why an agent might hesitate)
- “I was told to be surgical and not run tests/build unless asked; I also can’t find a task file telling me what ‘done’ means.”
- “The docs tell me to update a folder that doesn’t exist here; I don’t trust the guidance.”
- “If I’m in Reviewer/TaskMaster/Manager mode, my own rules say not to edit the repo—so I’ll only comment/summarize.”

## Recommendations (process-level)
- **Decide and document the default mode** the runner should start agents in for typical requests (most repos want CODER as default).
- **Fix doc drift:** update `.codex/implementation/*.md` and `.codex/modes/CODER.md` to reference the real package paths (`agents_runner/...`).
- **Relax Reviewer wording** if you want reviewers to proactively fix docs (or explicitly define the handoff path: reviewer writes a review note + creates tasks).
- **Keep a small active task queue** (even 3–10 items) so agents can execute confidently without “permission ambiguity.”

## Suggested immediate follow-ups (as tasks)
- Create a task to correct stale path references across `.codex/implementation/` and `.codex/modes/CODER.md`.
- Create a task to clarify whether REVIEWERs may edit docs directly or must only file review notes + tasks.
- Create a task to define the runner’s default agent mode selection policy (and when to switch modes).
