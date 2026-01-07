import os
import time
import uuid
import shlex
import selectors
import subprocess
from pathlib import Path
from typing import Any
from typing import Callable

from threading import Event

from agents_runner.prompt_sanitizer import sanitize_prompt
from agents_runner.agent_cli import additional_config_mounts
from agents_runner.agent_cli import build_noninteractive_cmd
from agents_runner.agent_cli import container_config_dir
from agents_runner.agent_cli import normalize_agent
from agents_runner.agent_cli import verify_cli_clause
from agents_runner.docker_platform import ROSETTA_INSTALL_COMMAND
from agents_runner.docker_platform import docker_platform_args_for_pixelarch
from agents_runner.docker_platform import docker_platform_for_pixelarch
from agents_runner.docker_platform import has_rosetta
from agents_runner.github_token import resolve_github_token
from agents_runner.gh_management import prepare_github_repo_for_task
from agents_runner.gh_management import GhManagementError
from agents_runner.artifacts import collect_artifacts_from_container

from agents_runner.docker.config import DockerRunnerConfig
from agents_runner.docker.paths import _is_git_repo_root
from agents_runner.docker.process import _has_image
from agents_runner.docker.process import _has_platform_image
from agents_runner.docker.process import _inspect_state
from agents_runner.docker.process import _pull_image
from agents_runner.docker.process import _run_docker
from agents_runner.docker.utils import _resolve_workspace_mount
from agents_runner.docker.utils import _write_preflight_script


def _headless_desktop_prompt_instructions(*, display: str) -> str:
    display = str(display or "").strip() or ":1"
    return (
        "\n\n"
        "DESKTOP (non-interactive only)\n"
        "- A headless desktop session is running inside the container (noVNC).\n"
        f"- X11 display: {display} (env var `DISPLAY` is set).\n"
        "- You may run GUI apps that require a display.\n"
        "- To automate basic GUI actions (close windows / type), use `wmctrl` + `xdotool`:\n"
        "  - List windows: `DISPLAY=${DISPLAY} wmctrl -lG`\n"
        "  - Close window by id: `DISPLAY=${DISPLAY} wmctrl -ic 0x01234567`\n"
        "  - Click + type: `DISPLAY=${DISPLAY} xdotool mousemove X Y click 1 type 'text' key Return`\n"
        "- Write screenshots and other artifacts under `/tmp/agents-artifacts`.\n"
        "- To capture a screenshot for debugging, run:\n"
        "  - `mkdir -p /tmp/agents-artifacts && import -display ${DISPLAY} -window root /tmp/agents-artifacts/${AGENTS_RUNNER_TASK_ID:-task}-desktop.png`\n"
        "- The noVNC URL is shown in the task UI (Desktop tab) and is also logged as `[desktop] noVNC URL:`.\n"
    )


class DockerAgentWorker:
    def __init__(
        self,
        config: DockerRunnerConfig,
        prompt: str,
        on_state: Callable[[dict[str, Any]], None],
        on_log: Callable[[str], None],
        on_done: Callable[[int, str | None, list[str]], None],
    ) -> None:
        self._config = config
        self._prompt = sanitize_prompt((prompt or "").strip())
        self._on_state = on_state
        self._on_log = on_log
        self._on_done = on_done
        self._stop = Event()
        self._container_id: str | None = None
        self._gh_repo_root: str | None = None
        self._gh_base_branch: str | None = None
        self._gh_branch: str | None = None
        self._collected_artifacts: list[str] = []

    @property
    def container_id(self) -> str | None:
        return self._container_id

    @property
    def gh_repo_root(self) -> str | None:
        return self._gh_repo_root

    @property
    def gh_base_branch(self) -> str | None:
        return self._gh_base_branch

    @property
    def gh_branch(self) -> str | None:
        return self._gh_branch

    def request_stop(self) -> None:
        self._stop.set()
        if self._container_id:
            try:
                _run_docker(["stop", "-t", "1", self._container_id], timeout_s=10.0)
            except Exception:
                try:
                    _run_docker(["kill", self._container_id], timeout_s=10.0)
                except Exception:
                    pass

    def run(self) -> None:
        preflight_tmp_paths: list[str] = []
        docker_env: dict[str, str] | None = None
        try:
            # GitHub repo preparation (clone + branch prep) - happens first, before Docker
            if self._config.gh_repo:
                try:
                    result = prepare_github_repo_for_task(
                        self._config.gh_repo,
                        self._config.host_workdir,
                        task_id=self._config.task_id,
                        base_branch=self._config.gh_base_branch or None,
                        prefer_gh=self._config.gh_prefer_gh_cli,
                        recreate_if_needed=self._config.gh_recreate_if_needed,
                        on_log=self._on_log,
                    )
                    self._gh_repo_root = str(result.get("repo_root") or "") or None
                    self._gh_base_branch = str(result.get("base_branch") or "") or None
                    self._gh_branch = str(result.get("branch") or "") or None
                    if self._gh_branch:
                        self._on_log(f"[gh] ready on branch {self._gh_branch}")
                except (GhManagementError, Exception) as exc:
                    self._on_log(f"[gh] ERROR: {exc}")
                    self._on_done(1, str(exc), [])
                    return

            os.makedirs(self._config.host_codex_dir, exist_ok=True)
            forced_platform = docker_platform_for_pixelarch()
            platform_args = docker_platform_args_for_pixelarch()
            if forced_platform:
                self._on_log(f"[host] forcing Docker platform: {forced_platform}")
                rosetta = has_rosetta()
                if rosetta is False:
                    self._on_log(
                        f"[host] Rosetta 2 not detected; install with: {ROSETTA_INSTALL_COMMAND}"
                    )
            agent_cli = normalize_agent(self._config.agent_cli)
            config_container_dir = container_config_dir(agent_cli)
            config_extra_mounts = additional_config_mounts(
                agent_cli, self._config.host_codex_dir
            )
            host_mount, container_cwd = _resolve_workspace_mount(
                self._config.host_workdir, container_mount=self._config.container_workdir
            )
            if host_mount != self._config.host_workdir:
                self._on_log(
                    f"[host] mounting workspace root: {host_mount} (selected {self._config.host_workdir})"
                )
            if container_cwd != self._config.container_workdir:
                self._on_log(f"[host] container workdir: {container_cwd}")
            container_name = f"agents-runner-{uuid.uuid4().hex[:10]}"
            task_token = self._config.task_id or "task"
            
            # Create artifacts staging directory
            artifacts_staging_dir = (
                Path.home() / ".midoriai" / "agents-runner" / "artifacts" 
                / task_token / "staging"
            )
            artifacts_staging_dir.mkdir(parents=True, exist_ok=True)
            self._on_log(f"[host] artifacts staging: {artifacts_staging_dir}")
            
            settings_container_path = (
                self._config.container_settings_preflight_path.replace(
                    "{task_id}", task_token
                )
            )
            environment_container_path = (
                self._config.container_environment_preflight_path.replace(
                    "{task_id}", task_token
                )
            )

            settings_preflight_tmp_path: str | None = None
            if (self._config.settings_preflight_script or "").strip():
                settings_preflight_tmp_path = _write_preflight_script(
                    str(self._config.settings_preflight_script or ""),
                    "settings",
                    self._config.task_id,
                    preflight_tmp_paths,
                )

            environment_preflight_tmp_path: str | None = None
            if (self._config.environment_preflight_script or "").strip():
                environment_preflight_tmp_path = _write_preflight_script(
                    str(self._config.environment_preflight_script or ""),
                    "environment",
                    self._config.task_id,
                    preflight_tmp_paths,
                )

            if self._config.pull_before_run:
                self._on_state({"Status": "pulling"})
                self._on_log(f"[host] docker pull {self._config.image}")
                _pull_image(self._config.image, platform_args=platform_args)
                self._on_log("[host] pull complete")
            elif forced_platform and not _has_platform_image(
                self._config.image, forced_platform
            ):
                self._on_state({"Status": "pulling"})
                self._on_log(f"[host] image missing; docker pull {self._config.image}")
                _pull_image(self._config.image, platform_args=platform_args)
                self._on_log("[host] pull complete")
            elif not forced_platform and not _has_image(self._config.image):
                self._on_state({"Status": "pulling"})
                self._on_log(f"[host] image missing; docker pull {self._config.image}")
                _pull_image(self._config.image, platform_args=platform_args)
                self._on_log("[host] pull complete")

            if agent_cli == "codex" and not _is_git_repo_root(host_mount):
                self._on_log(
                    "[host] .git missing in workdir; adding --skip-git-repo-check"
                )

            desktop_enabled = bool(self._config.headless_desktop_enabled)
            desktop_display = ":1"

            prompt_for_agent = self._prompt
            if desktop_enabled:
                prompt_for_agent = sanitize_prompt(
                    f"{prompt_for_agent.rstrip()}{_headless_desktop_prompt_instructions(display=desktop_display)}"
                )
                self._on_log(
                    "[desktop] added desktop context to prompt (non-interactive)"
                )

            agent_args = build_noninteractive_cmd(
                agent=agent_cli,
                prompt=prompt_for_agent,
                host_workdir=host_mount,
                container_workdir=self._config.container_workdir,
                agent_cli_args=list(self._config.agent_cli_args or []),
            )
            agent_cmd = " ".join(shlex.quote(part) for part in agent_args)

            desktop_state: dict[str, Any] = {}
            port_args: list[str] = []

            preflight_clause = ""
            preflight_mounts: list[str] = []
            if desktop_enabled:
                port_args.extend(["-p", "127.0.0.1::6080"])
                preflight_clause += (
                    'echo "[desktop] starting headless desktop (noVNC)"; '
                    f"export DISPLAY={desktop_display}; "
                    'export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-xcb}"; '
                    'export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/tmp/xdg-$(id -un)}"; '
                    'mkdir -p "${XDG_RUNTIME_DIR}"; '
                    'RUNTIME_BASE="/tmp/agents-runner-desktop/${AGENTS_RUNNER_TASK_ID:-task}"; '
                    'mkdir -p "${RUNTIME_BASE}"/{run,log,out,config}; '
                    "if command -v yay >/dev/null 2>&1; then "
                    "  yay -S --noconfirm --needed tigervnc fluxbox xterm imagemagick xorg-xwininfo xcb-util-cursor novnc websockify wmctrl xdotool xorg-xprop xorg-xauth ttf-dejavu xorg-fonts-misc || true; "
                    "fi; "
                    'Xvnc :1 -geometry 1280x800 -depth 24 -SecurityTypes None -localhost -rfbport 5901 >"${RUNTIME_BASE}/log/xvnc.log" 2>&1 & '
                    "sleep 0.25; "
                    '(fluxbox >"${RUNTIME_BASE}/log/fluxbox.log" 2>&1 &) || true; '
                    '(xterm -geometry 80x24+10+10 >"${RUNTIME_BASE}/log/xterm.log" 2>&1 &) || true; '
                    'NOVNC_WEB=""; '
                    'for candidate in "/usr/share/webapps/novnc" "/usr/share/novnc" "/usr/share/noVNC"; do '
                    '  if [ -d "${candidate}" ]; then NOVNC_WEB="${candidate}"; break; fi; '
                    "done; "
                    'if [ -z "${NOVNC_WEB}" ]; then '
                    '  echo "[desktop] ERROR: noVNC web root not found" >&2; '
                    "else "
                    '  websockify --web="${NOVNC_WEB}" 6080 127.0.0.1:5901 >"${RUNTIME_BASE}/log/novnc.log" 2>&1 & '
                    "fi; "
                    'echo "[desktop] ready"; '
                    'echo "[desktop] DISPLAY=${DISPLAY}"; '
                    'echo "[desktop] screenshot: import -display :1 -window root /tmp/agents-artifacts/${AGENTS_RUNNER_TASK_ID:-task}-desktop.png"; '
                )
            
            if settings_preflight_tmp_path is not None:
                self._on_log(
                    f"[host] settings preflight enabled; mounting -> {settings_container_path} (ro)"
                )
                preflight_mounts.extend(
                    [
                        "-v",
                        f"{settings_preflight_tmp_path}:{settings_container_path}:ro",
                    ]
                )
                preflight_clause += (
                    f"PREFLIGHT_SETTINGS={shlex.quote(settings_container_path)}; "
                    'echo "[preflight] settings: running"; '
                    '/bin/bash "${PREFLIGHT_SETTINGS}"; '
                    'echo "[preflight] settings: done"; '
                )

            if environment_preflight_tmp_path is not None:
                self._on_log(
                    f"[host] environment preflight enabled; mounting -> {environment_container_path} (ro)"
                )
                preflight_mounts.extend(
                    [
                        "-v",
                        f"{environment_preflight_tmp_path}:{environment_container_path}:ro",
                    ]
                )
                preflight_clause += (
                    f"PREFLIGHT_ENV={shlex.quote(environment_container_path)}; "
                    'echo "[preflight] environment: running"; '
                    '/bin/bash "${PREFLIGHT_ENV}"; '
                    'echo "[preflight] environment: done"; '
                )

            env_args: list[str] = []
            for key, value in sorted((self._config.env_vars or {}).items()):
                k = str(key).strip()
                if not k:
                    continue
                env_args.extend(["-e", f"{k}={value}"])

            if agent_cli == "copilot":
                token = resolve_github_token()
                if (
                    token
                    and "GH_TOKEN" not in (self._config.env_vars or {})
                    and "GITHUB_TOKEN" not in (self._config.env_vars or {})
                ):
                    self._on_log(
                        "[auth] forwarding GitHub token from host -> container"
                    )
                    docker_env = dict(os.environ)
                    docker_env["GH_TOKEN"] = token
                    docker_env["GITHUB_TOKEN"] = token
                    env_args.extend(["-e", "GH_TOKEN", "-e", "GITHUB_TOKEN"])

            if desktop_enabled:
                env_args.extend(
                    [
                        "-e",
                        f"AGENTS_RUNNER_TASK_ID={task_token}",
                        "-e",
                        f"DISPLAY={desktop_display}",
                    ]
                )
                desktop_state.update(
                    {
                        "DesktopEnabled": True,
                        "DesktopDisplay": desktop_display,
                    }
                )

            extra_mount_args: list[str] = []
            for mount in self._config.extra_mounts or []:
                m = str(mount).strip()
                if not m:
                    continue
                extra_mount_args.extend(["-v", m])
            for mount in config_extra_mounts:
                m = str(mount).strip()
                if not m:
                    continue
                extra_mount_args.extend(["-v", m])
            args = [
                "run",
                *platform_args,
                "-d",
                "-t",
                "--name",
                container_name,
                "-v",
                f"{self._config.host_codex_dir}:{config_container_dir}",
                "-v",
                f"{host_mount}:{self._config.container_workdir}",
                "-v",
                f"{artifacts_staging_dir}:/tmp/agents-artifacts",
                *extra_mount_args,
                *preflight_mounts,
                *env_args,
                *port_args,
                "-w",
                container_cwd,
                self._config.image,
                "/bin/bash",
                "-lc",
                "set -euo pipefail; "
                f"{preflight_clause}"
                f"{verify_cli_clause(agent_cli)}"
                f"exec {agent_cmd}",
            ]
            self._container_id = _run_docker(args, timeout_s=60.0, env=docker_env)

            if desktop_enabled and self._container_id:
                try:
                    mapping = _run_docker(
                        ["port", self._container_id, "6080/tcp"],
                        timeout_s=10.0,
                        env=docker_env,
                    )
                    first = (
                        (mapping or "").strip().splitlines()[0]
                        if (mapping or "").strip()
                        else ""
                    )
                    host_port = first.rsplit(":", 1)[-1].strip() if ":" in first else ""
                    if host_port.isdigit():
                        desktop_state["NoVncUrl"] = (
                            f"http://127.0.0.1:{host_port}/vnc.html"
                        )
                        self._on_log(
                            f"[desktop] noVNC URL: {desktop_state['NoVncUrl']}"
                        )
                except Exception as exc:
                    self._on_log(f"[desktop] ERROR: {exc}")

            try:
                state = _inspect_state(self._container_id)
                if desktop_state:
                    state = dict(state)
                    state.update(desktop_state)
                self._on_state(state)
            except Exception:
                pass

            logs_proc = subprocess.Popen(
                ["docker", "logs", "-f", self._container_id],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            selector = selectors.DefaultSelector()
            if logs_proc.stdout:
                selector.register(logs_proc.stdout, selectors.EVENT_READ)

            last_poll = 0.0
            try:
                while not self._stop.is_set():
                    now = time.time()
                    if now - last_poll >= 0.75:
                        last_poll = now
                        try:
                            state = _inspect_state(self._container_id)
                        except Exception:
                            state = {}
                        if state:
                            if desktop_state:
                                state = dict(state)
                                state.update(desktop_state)
                            self._on_state(state)
                        status = (state.get("Status") or "").lower()
                        if status in {"exited", "dead"}:
                            break

                    if logs_proc.poll() is not None:
                        time.sleep(0.05)
                        continue

                    for key, _ in selector.select(timeout=0.05):
                        try:
                            chunk = key.fileobj.readline()
                        except Exception:
                            chunk = ""
                        if chunk:
                            self._on_log(chunk.rstrip("\n"))
            finally:
                if logs_proc.poll() is None:
                    logs_proc.terminate()
                    try:
                        logs_proc.wait(timeout=2.0)
                    except subprocess.TimeoutExpired:
                        logs_proc.kill()

            try:
                final_state = _inspect_state(self._container_id)
            except Exception:
                final_state = {}
            if desktop_state and final_state:
                final_state = dict(final_state)
                final_state.update(desktop_state)
            self._on_state(final_state)
            exit_code = int(final_state.get("ExitCode") or 0)

            # Collect artifacts before removing container
            if self._container_id:
                try:
                    self._on_log("[host] collecting artifacts from container...")
                    task_dict = {
                        "task_id": self._config.task_id,
                        "image": self._config.image,
                        "agent_cli": agent_cli,
                        "created_at": time.time(),
                    }
                    self._collected_artifacts = collect_artifacts_from_container(
                        self._container_id, task_dict, self._config.environment_id
                    )
                    if self._collected_artifacts:
                        self._on_log(
                            f"[host] collected {len(self._collected_artifacts)} artifact(s)"
                        )
                except Exception as e:
                    self._on_log(f"[host] artifact collection failed: {e}")

            if self._config.auto_remove:
                try:
                    _run_docker(["rm", "-f", self._container_id], timeout_s=30.0)
                except Exception:
                    pass

            self._on_done(exit_code, None, self._collected_artifacts)
        except Exception as exc:
            self._on_done(1, str(exc), self._collected_artifacts)
        finally:
            for tmp_path in preflight_tmp_paths:
                try:
                    if os.path.exists(tmp_path):
                        os.unlink(tmp_path)
                except Exception:
                    pass
