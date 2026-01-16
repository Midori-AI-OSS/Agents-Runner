# Task — Refactor Task Details layout (logs left, details right)

## 1. Title (short)
Task Details: logs left, details right

## 2. Summary (1–3 sentences)
Refactor the Task Details “Task” tab layout so logs occupy the full left side, while container state + prompt/details stack on the right. Remove the `Host Config folder` field entirely, and hide `Host Workdir` for cloned-workspace tasks.

## 3. Implementation notes (key decisions + constraints)
- Target file: `agents_runner/ui/pages/task_details.py`.
- Current layout:
  - `mid` row: left = `Prompt` card (prompt + host workdir/config + container id), right = `Container state` card.
  - `Logs` card is below and spans full width.
- Desired layout:
  - `mid` row: left = `Logs` card (full-height in left column), right = vertical stack:
    1) `Container state` card (unchanged controls/status)
    2) `Prompt` + metadata card (prompt text, plus container id and host workdir when applicable)
- Field removals/conditions:
  - Remove `Host Config folder` label/value entirely (no widget, no update code).
  - Hide `Host Workdir` for cloned-based envs (use `task.workspace_type` and compare to `agents_runner.environments.WORKSPACE_CLONED`).
  - Keep `Container ID` visible and selectable.
- Prompt copy UX:
  - Add a `Copy` button for the Prompt box that copies the full prompt text to clipboard.
  - Keep button styling consistent with existing `QToolButton` usage; no rounded corners.
- Keep UI styling consistent and sharp (no rounded corners).
- Keep diffs minimal; don’t change Desktop/Artifacts behavior in this task.

## 4. Acceptance criteria (clear, testable statements)
- In Task Details → `Task` tab:
  - Logs take the full left side (primary column) of the view.
  - The right side shows `Container state` with actions, and below it the `Prompt` panel (prompt + metadata).
- `Host Config folder` is fully removed from the UI (no label/value, no updates in `show_task` / `update_task`).
- `Host Workdir` is not displayed for tasks where `task.workspace_type == WORKSPACE_CLONED`.
- `Container ID` remains visible and selectable, and is still updated live.
- Prompt has a `Copy` button that copies the full prompt to clipboard.

## 5. Expected files to modify (explicit paths)
- `agents_runner/ui/pages/task_details.py`

## 6. Out of scope (what not to do)
- Do not add tests or update `README.md`.
