# Headless Desktop Instructions

This prompt teaches the agent how to interact with GUI applications in the noVNC headless desktop environment.

**When used:** Headless desktop is enabled (Settings or per-environment)  
**Template variables:** `{DISPLAY}` - X11 display identifier (default: ":1")

## Prompt


DESKTOP (non-interactive only)
- A headless desktop session is running inside the container (noVNC).
- X11 display: {DISPLAY} (env var `DISPLAY` is set).
- You may run GUI apps that require a display.
- To automate basic GUI actions (close windows / type), use `wmctrl` + `xdotool`:
  - List windows: `DISPLAY=${{DISPLAY}} wmctrl -lG`
  - Close window by id: `DISPLAY=${{DISPLAY}} wmctrl -ic 0x01234567`
  - Click + type: `DISPLAY=${{DISPLAY}} xdotool mousemove X Y click 1 type 'text' key Return`
- Write screenshots and other artifacts under `/tmp/agents-artifacts`.
- To capture a screenshot for debugging, run:
  - `mkdir -p /tmp/agents-artifacts && import -display ${{DISPLAY}} -window root /tmp/agents-artifacts/${{AGENTS_RUNNER_TASK_ID:-task}}-desktop.png`
- The noVNC URL is shown in the task UI (Desktop tab) and is also logged as `[desktop] noVNC URL:`.
