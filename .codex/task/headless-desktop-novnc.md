# Task: Headless Desktop + noVNC for Agents (with random free ports)

## Goal
Add an optional “Headless desktop (noVNC)” capability to Agents Runner so agents can run/test GUI apps (Qt/X11) and humans can view/control them via noVNC.

Key requirement: **a Settings checkbox** that, when enabled, makes **each run pick random, free host ports** for the desktop endpoint(s), so multiple agents can run concurrently without collisions.

Recommended architecture (matches current app design):
- Start the desktop stack **inside the per-task Docker container** (Xvnc + WM + noVNC/websockify).
- Expose **noVNC from the container to the host** via Docker `-p` using a random free host port.
  - Optionally also expose raw VNC similarly (useful for external VNC clients), but the in-app viewer should use noVNC.

When enabled, **preflight** should:
1) set up the desktop (Xvnc + lightweight WM)
2) start noVNC
3) **prompt the agent** with clear “how to use the desktop” instructions (DISPLAY, URLs, password, screenshot tips)

## What was done manually (reference)
This is how it was validated in this container:

Packages installed (Arch/PixelArch):
- `tigervnc` (provides `Xvnc`)
- `fluxbox` (WM)
- `xterm` (sanity terminal)
- `imagemagick` (`import` screenshot tool)
- `xorg-xwininfo` (window enumeration)
- `xcb-util-cursor` (Qt xcb plugin dependency)
- also useful: `xorg-xauth`, fonts (`ttf-dejavu`, `xorg-fonts-misc`)

Manual run approach:
- Start `Xvnc :1` with `-SecurityTypes VncAuth -PasswordFile <file> -localhost -rfbport 5901`
- Start session on that display (fluxbox + xterm)
- Run app with `DISPLAY=:1 QT_QPA_PLATFORM=xcb uv run main.py`
- Screenshot with `import -display :1 -window root out.png`

Working artifacts from the manual proof:
- Runtime dir: `/home/midori-ai/tmp-headless-desktop/`
- Screenshot copied to: `.codex/temp/repo-app.png`

## Proposed implementation (repo changes)

### 1) Settings UI
Add a checkbox under Settings (wording suggestion):
- `Enable headless desktop (noVNC) for agents`
- When enabled, ports should always be random + free by default (this is the whole point of the feature).

Persist in existing settings system.

### 2) Desktop preflight hook
Integrate into the existing “Run Agent” container startup path (the code already builds a `docker run ...` command).

Concrete anchors in this repo:
- Container startup for agent runs: `agents_runner/docker/agent_worker.py`
- Runner config: `agents_runner/docker/config.py` (`DockerRunnerConfig`)
- Where the agent prompt is constructed before running: `agents_runner/ui/main_window_tasks_agent.py` (look for `runner_prompt`)
- Task viewer UI: `agents_runner/ui/pages/task_details.py` (`TaskDetailsPage`)

When the setting is enabled:
- Create a per-run runtime directory inside the container, e.g.:
  - `/tmp/agents-runner-desktop/<task_id>/` with `run/`, `log/`, `out/`, `config/`
- Install required desktop packages **inside the container** using `yay` non-interactively (PixelArch guarantee):
  - Use `yay -S --noconfirm --needed ...` (avoid `pacman` and avoid prompts).
  - If you need to refresh package metadata, prefer `yay -Sy --noconfirm` (avoid `-Syu` unless it’s required and stable).
- Start X server:
  - Prefer direct `Xvnc` invocation (systemd services are unreliable in this container)
  - Use `-localhost` by default (VNC should only be reachable from inside the container)
  - Use VNC auth with a password file (generate a random password per run)
- Start WM/session:
  - `fluxbox` is sufficient; also spawn `xterm` for debugging
  - Ensure `XDG_RUNTIME_DIR` exists (some environments don’t set `USER`; use `id -un`)
- Start noVNC:
  - Run `websockify --web=/usr/share/novnc/ 6080 127.0.0.1:5901` (container-local ports)
  - If the project wants a nicer URL, wrap with a helper that prints the full link to `vnc.html`

### 3) Random *free* ports (critical requirement)
Doable, but the least-racy approach with Docker is to let Docker pick the host port and then read it back.

Recommended port strategy:
- Use fixed container ports (e.g. `5901` for VNC and `6080` for noVNC) inside the container.
- Use random host port mappings:
  - noVNC: `-p 127.0.0.1::6080`
  - optional VNC: `-p 127.0.0.1::5901`
- After `docker run`, resolve the chosen host port via `docker port <container_id> 6080/tcp` (or `docker inspect`).

If docker is involved:
- Identify where `docker run` args are created (see `agents_runner/docker/agent_worker.py`) and add the `-p` mappings when the setting is enabled.
- Store the resolved noVNC URL (`http://127.0.0.1:<port>/vnc.html`) on the `Task` so the UI can embed it.

### 4) Task Viewer prompt/info container box shows the desktop
When desktop is ready, the **Task Viewer prompt + info container box** should **display the desktop itself** (embedded noVNC view).

UX requirement (explicit):
- While the desktop is running for the task’s container, the prompt + info content **should not be shown** in that box (replace it with the desktop view).

It should still be clear that:
- the **container for this task** is where the VNC/noVNC desktop will appear while the task is running
- the desktop is **per-task/per-container** (so multiple tasks can have their own desktops if ports are free)

Implementation suggestion:
- The prompt/info container box embeds noVNC (use `PySide6.QtWebEngineWidgets.QWebEngineView`) pointing at the per-task noVNC endpoint.
- Implement as a `QStackedLayout` or `QStackedWidget` in `agents_runner/ui/pages/task_details.py` so you can swap:
  - “Prompt + info” view (default / when desktop disabled / after task ends)
  - “Desktop” view (while the task is active and desktop enabled)
- Still show a compact “Desktop details” block near the embedded view:
  - Status: `starting/running/stopped`
  - noVNC URL + “copy” button (useful for opening externally)
  - VNC password (or “reveal”)
  - `DISPLAY` value and example command snippets

Include quick “how to use” instructions (Like how we do with pixelarch prompt or the gh pr prompt), e.g.:
- `DISPLAY=:<n>` and “run GUI commands with DISPLAY set”
- noVNC URL (localhost) and guidance to tunnel if needed
- VNC password (or where to read it); keep it scoped to the run
- how to take screenshots (either a built-in helper command or `import -display :<n> -window root ...`)
- log locations (`xvnc.log`, `novnc.log`)

Note: explicit cleanup/teardown is not required here because the program removes the container after each use.

## Must-verify items (do not assume)
- Confirm the correct noVNC web root path inside the container (Arch typically uses `/usr/share/novnc/`, but the setup script should detect/locate it).
- Confirm `PySide6.QtWebEngineWidgets` works in the host app runtime (it imports in this dev container, but packaging/runtime environments may differ).
- Confirm where “prompt + info container box” should live visually:
  - Likely `agents_runner/ui/pages/task_details.py` left-side card (“Prompt”); add a desktop panel/tab there.

## Acceptance criteria
- Toggling the Settings checkbox enables/disables the feature.
- With the feature enabled, starting 2+ agents concurrently results in:
  - distinct, working noVNC endpoints (different ports)
  - no port conflicts for docker mappings (if applicable)
- The Task Viewer prompt/info container box shows the desktop (embedded) and the agent/user can follow the instructions immediately.
- A simple Qt GUI app (this repo’s `uv run main.py`) opens successfully on the headless desktop.
- Optional: provide a “capture screenshot” helper that writes into the per-run `out/` folder.
