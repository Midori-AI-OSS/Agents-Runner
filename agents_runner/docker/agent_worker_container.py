"""Container execution logic for Docker agent workers.

Handles Docker container orchestration including:
- Agent command building
- Desktop/VNC setup (cached and runtime variants)
- Preflight script execution
- Environment variable forwarding
- Container lifecycle management via unified planner/runner
- Artifact collection

Usage Example:
    from agents_runner.docker.agent_worker_setup import WorkerSetup
    from agents_runner.docker.agent_worker_container import ContainerExecutor

    # Prepare runtime environment
    setup = WorkerSetup(config, prompt, on_log, on_state)
    runtime_env = setup.prepare_runtime_environment(preflight_tmp_paths)

    # Execute container
    executor = ContainerExecutor(config, runtime_env, on_state, on_log, stop_event)
    exit_code = executor.execute_container()
"""

import os
import selectors
import shlex
import subprocess
import time
from pathlib import Path
from typing import Any, Callable

from agents_runner.agent_cli import build_noninteractive_cmd, verify_cli_clause
from agents_runner.github_token import resolve_github_token
from agents_runner.log_format import format_log, wrap_container_log
from agents_runner.core.shell_templates import git_identity_clause, shell_log_statement
from agents_runner.planner import (
    DockerSpec,
    ExecSpec,
    MountSpec,
    RunPlan,
    SubprocessDockerAdapter,
    execute_plan,
)

from agents_runner.docker.config import DockerRunnerConfig
from agents_runner.docker.process import _run_docker, _inspect_state
from agents_runner.docker.agent_worker_setup import RuntimeEnvironment
from agents_runner.docker.utils import deduplicate_mounts
from agents_runner.environments import load_environments


def _is_gh_context_enabled(environment_id: str | None) -> bool:
    """Check if GitHub Context is enabled in environment settings."""
    if not environment_id:
        return False
    try:
        environments = load_environments()
        env = environments.get(str(environment_id))
    except Exception:
        return False
    if env is None:
        return False
    return bool(getattr(env, "gh_context_enabled", False))


def _needs_cross_agent_gh_token(environment_id: str | None) -> bool:
    """Check if copilot is in the cross-agent allowlist."""
    if not environment_id:
        return False
    try:
        environments = load_environments()
        env = environments.get(str(environment_id))
    except Exception:
        return False
    if env is None or not env.cross_agent_allowlist:
        return False
    if env.agent_selection is None or not env.agent_selection.agents:
        return False

    from agents_runner.agent_cli import normalize_agent

    agent_cli_by_id: dict[str, str] = {
        agent.agent_id: agent.agent_cli for agent in env.agent_selection.agents
    }

    for agent_id in env.cross_agent_allowlist:
        agent_cli = agent_cli_by_id.get(agent_id)
        if agent_cli and normalize_agent(agent_cli) == "copilot":
            return True
    return False


class ContainerExecutor:
    """Handles Docker container execution for agent workers."""

    def __init__(
        self,
        config: DockerRunnerConfig,
        runtime_env: RuntimeEnvironment,
        on_state: Callable[[dict[str, Any]], None],
        on_log: Callable[[str], None],
        stop_event: Any,  # threading.Event
    ) -> None:
        """Initialize container executor.

        Args:
            config: Docker runner configuration
            runtime_env: Prepared runtime environment
            on_state: Callback for state updates
            on_log: Callback for log messages
            stop_event: Event for stopping execution
        """
        self._config = config
        self._runtime_env = runtime_env
        self._on_state = on_state
        self._on_log = on_log
        self._stop = stop_event
        self._container_id: str | None = None

    @property
    def container_id(self) -> str | None:
        """Get the container ID."""
        return self._container_id

    def execute_container(self) -> int:
        """Execute the agent container using unified planner/runner.

        Returns:
            Container exit code (0 for success, non-zero for failure)
        """
        try:
            # Check for unsupported features
            if self._runtime_env.desktop_enabled:
                self._on_log(
                    format_log(
                        "docker",
                        "runner",
                        "ERROR",
                        "Desktop mode not yet supported in unified runner",
                    )
                )
                return 1

            # Build agent command
            agent_args = self._build_agent_command()
            agent_cmd = " ".join(shlex.quote(part) for part in agent_args)

            # Setup desktop state tracking
            desktop_state: dict[str, Any] = {}

            # Build preflight clause and mounts
            preflight_clause, preflight_mounts = self._build_preflight_clause(
                desktop_state
            )

            # Build environment variables dict
            env_dict = self._build_env_dict()

            # Build complete bash command (preflight + agent)
            bash_cmd = self._build_bash_command(preflight_clause, agent_cmd)

            # Build mounts list
            mounts = self._build_mounts(preflight_mounts)

            # Create run plan using planner models
            plan = self._create_run_plan(bash_cmd, mounts, env_dict)

            # Execute plan using unified runner
            self._on_log(format_log("docker", "runner", "INFO", "starting container"))
            adapter = SubprocessDockerAdapter()
            result = execute_plan(plan, adapter)

            # Store container ID from plan
            self._container_id = plan.docker.container_name

            # Report final state
            self._report_state(desktop_state)

            # Log execution result
            if result.exit_code == 0:
                self._on_log(
                    format_log(
                        "docker", "runner", "INFO", "task completed successfully"
                    )
                )
            else:
                self._on_log(
                    format_log(
                        "docker",
                        "runner",
                        "ERROR",
                        f"task failed with exit code {result.exit_code}",
                    )
                )

            # Log stdout/stderr if present
            if result.stdout:
                self._on_log(result.stdout.decode("utf-8", errors="replace"))
            if result.stderr:
                self._on_log(result.stderr.decode("utf-8", errors="replace"))

            return result.exit_code

        except Exception as exc:
            self._on_log(format_log("docker", "container", "ERROR", str(exc)))
            return 1

    def _build_agent_command(self) -> list[str]:
        """Build the agent CLI command."""
        return build_noninteractive_cmd(
            agent=self._runtime_env.agent_cli,
            prompt=self._runtime_env.prompt_for_agent,
            host_workdir=self._runtime_env.host_mount,
            container_workdir=self._config.container_workdir,
            agent_cli_args=list(self._config.agent_cli_args or []),
        )

    def _build_preflight_clause(
        self, desktop_state: dict[str, Any]
    ) -> tuple[str, list[str]]:
        """Build preflight clause and mounts. Returns (clause, mounts)."""
        preflight_clause = ""
        preflight_mounts: list[str] = []

        # Desktop preflight
        if self._runtime_env.desktop_enabled:
            preflight_clause += self._build_desktop_preflight_clause()
            desktop_state.update(
                {
                    "DesktopEnabled": True,
                    "DesktopDisplay": self._runtime_env.desktop_display,
                }
            )

        # Settings preflight
        if self._runtime_env.settings_preflight_tmp_path is not None:
            clause, mounts = self._build_settings_preflight(
                self._runtime_env.settings_preflight_tmp_path,
                self._runtime_env.settings_container_path,
            )
            preflight_clause += clause
            preflight_mounts.extend(mounts)

        # Environment preflight
        if self._runtime_env.environment_preflight_tmp_path is not None:
            clause, mounts = self._build_environment_preflight(
                self._runtime_env.environment_preflight_tmp_path,
                self._runtime_env.environment_container_path,
            )
            preflight_clause += clause
            preflight_mounts.extend(mounts)

        return preflight_clause, preflight_mounts

    def _build_bash_command(self, preflight_clause: str, agent_cmd: str) -> str:
        """Build complete bash command with preflight and agent execution.

        Args:
            preflight_clause: Bash commands for preflight setup
            agent_cmd: Agent CLI command to execute

        Returns:
            Complete bash command string
        """
        return (
            "set -euo pipefail; "
            f"{git_identity_clause()}"
            f"{preflight_clause}"
            f"{verify_cli_clause(self._runtime_env.agent_cli)}"
            f"exec {agent_cmd}"
        )

    def _build_env_dict(self) -> dict[str, str]:
        """Build environment variables dictionary.

        Returns:
            Dictionary of environment variables for the container
        """
        env_dict: dict[str, str] = {}

        # Add configured env vars
        for key, value in sorted((self._config.env_vars or {}).items()):
            k = str(key).strip()
            if k:
                env_dict[k] = str(value)

        # Forward GitHub tokens if needed
        needs_token = (
            _is_gh_context_enabled(self._config.environment_id)
            or self._runtime_env.agent_cli == "copilot"
            or _needs_cross_agent_gh_token(self._config.environment_id)
        )

        if needs_token:
            token = resolve_github_token()
            if token and "GH_TOKEN" not in env_dict and "GITHUB_TOKEN" not in env_dict:
                self._on_log("[auth] forwarding GitHub token from host -> container")
                env_dict["GH_TOKEN"] = token
                env_dict["GITHUB_TOKEN"] = token

        # Add desktop env vars if enabled
        if self._runtime_env.desktop_enabled:
            env_dict["AGENTS_RUNNER_TASK_ID"] = str(self._runtime_env.task_token)
            env_dict["DISPLAY"] = str(self._runtime_env.desktop_display)

        return env_dict

    def _build_mounts(self, preflight_mounts: list[str]) -> list[MountSpec]:
        """Build list of mount specifications.

        Args:
            preflight_mounts: Additional mount strings for preflight scripts

        Returns:
            List of MountSpec objects for the container
        """
        # Collect all mount strings first
        all_mounts: list[str] = []

        # Add primary config mount
        all_mounts.append(
            f"{self._config.host_codex_dir}:{self._runtime_env.config_container_dir}"
        )

        # Add workspace mount
        all_mounts.append(
            f"{self._runtime_env.host_mount}:{self._config.container_workdir}"
        )

        # Add artifacts mount
        all_mounts.append(
            f"{self._runtime_env.artifacts_staging_dir}:/tmp/agents-artifacts"
        )

        # Add extra mounts from config
        for mount in self._config.extra_mounts or []:
            m = str(mount).strip()
            if m:
                all_mounts.append(m)

        # Add config extra mounts (cross-agent configs, etc.)
        for mount in self._runtime_env.config_extra_mounts:
            m = str(mount).strip()
            if m:
                all_mounts.append(m)

        # Add preflight mounts
        for mount in preflight_mounts:
            m = str(mount).strip()
            if m:
                all_mounts.append(m)

        # Deduplicate by container path, preserving order
        deduplicated = deduplicate_mounts(all_mounts)

        # Parse mount strings into MountSpec objects
        mount_specs: list[MountSpec] = []
        for mount_str in deduplicated:
            parts = mount_str.split(":")
            if len(parts) >= 2:
                src = Path(parts[0])
                dst = Path(parts[1])
                mode = parts[2] if len(parts) > 2 and parts[2] in ("ro", "rw") else "rw"
                # Only add if paths are absolute
                if src.is_absolute() and dst.is_absolute():
                    mount_specs.append(MountSpec(src=src, dst=dst, mode=mode))  # type: ignore

        return mount_specs

    def _create_run_plan(
        self, bash_cmd: str, mounts: list[MountSpec], env_dict: dict[str, str]
    ) -> RunPlan:
        """Create a RunPlan for execution.

        Args:
            bash_cmd: Complete bash command to execute
            mounts: List of mount specifications
            env_dict: Environment variables dictionary

        Returns:
            RunPlan ready for execution
        """
        # Create docker spec
        docker_spec = DockerSpec(
            image=self._runtime_env.runtime_image,
            container_name=self._runtime_env.container_name,
            workdir=Path(self._runtime_env.container_cwd),
            mounts=mounts,
            env=env_dict,
        )

        # Create exec spec for bash command
        exec_spec = ExecSpec(
            argv=["/bin/bash", "-lc", bash_cmd],
            cwd=Path(self._runtime_env.container_cwd),
            tty=False,
            stdin=False,
        )

        # Create artifact spec (artifacts already mounted to /tmp/agents-artifacts)
        from agents_runner.planner.models import ArtifactSpec

        artifacts = ArtifactSpec(
            finish_file=Path("/tmp/agents-artifacts/FINISH"),
            output_file=Path("/tmp/agents-artifacts/agent-output.md"),
        )

        # Create run plan
        return RunPlan(
            interactive=False,
            docker=docker_spec,
            prompt_text="",  # Prompt already embedded in bash command
            exec_spec=exec_spec,
            artifacts=artifacts,
        )

    def _build_desktop_preflight_clause(self) -> str:
        """Build desktop preflight clause based on cached vs runtime setup."""
        using_cached_image = self._runtime_env.runtime_image != self._config.image
        if using_cached_image:
            self._on_log(
                format_log(
                    "desktop",
                    "setup",
                    "INFO",
                    "using pre-installed desktop from cached image",
                )
            )
            return self._build_desktop_cached_preflight(
                self._runtime_env.desktop_display
            )
        return self._build_desktop_runtime_preflight(self._runtime_env.desktop_display)

    def _build_desktop_cached_preflight(self, desktop_display: str) -> str:
        """Build preflight clause for cached desktop image."""
        common_setup = (
            f"{shell_log_statement('desktop', 'vnc', 'INFO', 'starting headless desktop (noVNC)')}; "
            f"export DISPLAY={desktop_display}; "
            'export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-xcb}"; '
            'export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/tmp/xdg-$(id -un)}"; '
            'mkdir -p "${XDG_RUNTIME_DIR}"; '
            'RUNTIME_BASE="/tmp/agents-runner-desktop/${AGENTS_RUNNER_TASK_ID:-task}"; '
            'mkdir -p "${RUNTIME_BASE}"/{run,log,out,config}; '
        )
        novnc_setup = (
            "if [ -f /etc/default/novnc-path ]; then source /etc/default/novnc-path; else "
            'NOVNC_WEB=""; for candidate in "/usr/share/webapps/novnc" "/usr/share/novnc" "/usr/share/noVNC"; do '
            'if [ -d "${candidate}" ]; then NOVNC_WEB="${candidate}"; break; fi; done; fi; '
            "if [ -f /etc/profile.d/desktop-env.sh ]; then source /etc/profile.d/desktop-env.sh; fi; "
        )
        service_start = (
            'Xvnc :1 -geometry 1280x800 -depth 24 -SecurityTypes None -localhost -rfbport 5901 >"${RUNTIME_BASE}/log/xvnc.log" 2>&1 & sleep 0.25; '
            '(fluxbox >"${RUNTIME_BASE}/log/fluxbox.log" 2>&1 &) || true; '
            '(xterm -geometry 80x24+10+10 >"${RUNTIME_BASE}/log/xterm.log" 2>&1 &) || true; '
            'if [ -n "${NOVNC_WEB}" ]; then websockify --web="${NOVNC_WEB}" 6080 127.0.0.1:5901 >"${RUNTIME_BASE}/log/novnc.log" 2>&1 & '
            f"else {shell_log_statement('desktop', 'vnc', 'ERROR', 'noVNC web root not found')} >&2; fi; "
        )
        return (
            common_setup
            + novnc_setup
            + service_start
            + f"{shell_log_statement('desktop', 'vnc', 'INFO', 'ready')}; "
            f"{shell_log_statement('desktop', 'vnc', 'INFO', 'DISPLAY=${DISPLAY}')}; "
            f"{shell_log_statement('desktop', 'vnc', 'INFO', 'screenshot: import -display :1 -window root /tmp/agents-artifacts/${AGENTS_RUNNER_TASK_ID:-task}-desktop.png')}; "
        )

    def _build_desktop_runtime_preflight(self, desktop_display: str) -> str:
        """Build preflight clause for runtime desktop installation."""
        common_setup = (
            f"{shell_log_statement('desktop', 'vnc', 'INFO', 'starting headless desktop (noVNC)')}; "
            f"export DISPLAY={desktop_display}; "
            'export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-xcb}"; '
            'export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/tmp/xdg-$(id -un)}"; '
            'mkdir -p "${XDG_RUNTIME_DIR}"; '
            'RUNTIME_BASE="/tmp/agents-runner-desktop/${AGENTS_RUNNER_TASK_ID:-task}"; '
            'mkdir -p "${RUNTIME_BASE}"/{run,log,out,config}; '
        )
        install_packages = (
            "if command -v yay >/dev/null 2>&1; then "
            "yay -S --noconfirm --needed tigervnc fluxbox xterm imagemagick xorg-xwininfo xcb-util-cursor novnc websockify wmctrl xdotool xorg-xprop xorg-xauth ttf-dejavu xorg-fonts-misc || true; fi; "
        )
        service_start = (
            'Xvnc :1 -geometry 1280x800 -depth 24 -SecurityTypes None -localhost -rfbport 5901 >"${RUNTIME_BASE}/log/xvnc.log" 2>&1 & sleep 0.25; '
            '(fluxbox >"${RUNTIME_BASE}/log/fluxbox.log" 2>&1 &) || true; '
            '(xterm -geometry 80x24+10+10 >"${RUNTIME_BASE}/log/xterm.log" 2>&1 &) || true; '
            'NOVNC_WEB=""; for candidate in "/usr/share/webapps/novnc" "/usr/share/novnc" "/usr/share/noVNC"; do '
            'if [ -d "${candidate}" ]; then NOVNC_WEB="${candidate}"; break; fi; done; '
            'if [ -z "${NOVNC_WEB}" ]; then '
            f"{shell_log_statement('desktop', 'vnc', 'ERROR', 'noVNC web root not found')} >&2; "
            'else websockify --web="${NOVNC_WEB}" 6080 127.0.0.1:5901 >"${RUNTIME_BASE}/log/novnc.log" 2>&1 & fi; '
        )
        return (
            common_setup
            + install_packages
            + service_start
            + f"{shell_log_statement('desktop', 'vnc', 'INFO', 'ready')}; "
            f"{shell_log_statement('desktop', 'vnc', 'INFO', 'DISPLAY=${DISPLAY}')}; "
            f"{shell_log_statement('desktop', 'vnc', 'INFO', 'screenshot: import -display :1 -window root /tmp/agents-artifacts/${AGENTS_RUNNER_TASK_ID:-task}-desktop.png')}; "
        )

    def _build_settings_preflight(
        self, tmp_path: str, container_path: str
    ) -> tuple[str, list[str]]:
        """Build settings preflight clause and mounts."""
        self._on_log(
            format_log(
                "host",
                "none",
                "INFO",
                f"settings preflight enabled; mounting -> {container_path} (ro)",
            )
        )
        return (
            f"PREFLIGHT_SETTINGS={shlex.quote(container_path)}; "
            f"{shell_log_statement('env', 'setup', 'INFO', 'settings: running')}; "
            '/bin/bash "${PREFLIGHT_SETTINGS}"; '
            f"{shell_log_statement('env', 'setup', 'INFO', 'settings: done')}; ",
            ["-v", f"{tmp_path}:{container_path}:ro"],
        )

    def _build_environment_preflight(
        self, tmp_path: str, container_path: str
    ) -> tuple[str, list[str]]:
        """Build environment preflight clause and mounts."""
        self._on_log(
            format_log(
                "host",
                "none",
                "INFO",
                f"environment preflight enabled; mounting -> {container_path} (ro)",
            )
        )
        return (
            f"PREFLIGHT_ENV={shlex.quote(container_path)}; "
            f"{shell_log_statement('env', 'setup', 'INFO', 'environment: running')}; "
            '/bin/bash "${PREFLIGHT_ENV}"; '
            f"{shell_log_statement('env', 'setup', 'INFO', 'environment: done')}; ",
            ["-v", f"{tmp_path}:{container_path}:ro"],
        )

    def _build_env_args(self) -> tuple[list[str], dict[str, str] | None]:
        """Build environment variable arguments. Returns (env_args, docker_env)."""
        env_args: list[str] = []
        docker_env: dict[str, str] | None = None

        # Add configured env vars
        for key, value in sorted((self._config.env_vars or {}).items()):
            k = str(key).strip()
            if k:
                env_args.extend(["-e", f"{k}={value}"])

        # Forward GitHub tokens if needed
        needs_token = (
            _is_gh_context_enabled(self._config.environment_id)
            or self._runtime_env.agent_cli == "copilot"
            or _needs_cross_agent_gh_token(self._config.environment_id)
        )

        if needs_token:
            token = resolve_github_token()
            if (
                token
                and "GH_TOKEN" not in (self._config.env_vars or {})
                and "GITHUB_TOKEN" not in (self._config.env_vars or {})
            ):
                self._on_log("[auth] forwarding GitHub token from host -> container")
                docker_env = dict(os.environ)
                docker_env["GH_TOKEN"] = token
                docker_env["GITHUB_TOKEN"] = token
                env_args.extend(["-e", "GH_TOKEN", "-e", "GITHUB_TOKEN"])

        # Add desktop env vars if enabled
        if self._runtime_env.desktop_enabled:
            env_args.extend(
                [
                    "-e",
                    f"AGENTS_RUNNER_TASK_ID={self._runtime_env.task_token}",
                    "-e",
                    f"DISPLAY={self._runtime_env.desktop_display}",
                ]
            )

        return env_args, docker_env

    def _build_port_args(self) -> list[str]:
        """Build port mapping arguments."""
        port_args: list[str] = []
        if self._runtime_env.desktop_enabled:
            port_args.extend(["-p", "127.0.0.1::6080"])
        return port_args

    def _build_extra_mounts(self) -> list[str]:
        """Build extra mount arguments with deduplication."""
        # Collect all mount strings first (without -v flags)
        all_mounts: list[str] = []

        # Add primary config mount
        all_mounts.append(
            f"{self._config.host_codex_dir}:{self._runtime_env.config_container_dir}"
        )

        # Add workspace mount
        all_mounts.append(
            f"{self._runtime_env.host_mount}:{self._config.container_workdir}"
        )

        # Add artifacts mount
        all_mounts.append(
            f"{self._runtime_env.artifacts_staging_dir}:/tmp/agents-artifacts"
        )

        # Add extra mounts from config
        for mount in self._config.extra_mounts or []:
            m = str(mount).strip()
            if m:
                all_mounts.append(m)

        # Add config extra mounts (cross-agent configs, etc.)
        for mount in self._runtime_env.config_extra_mounts:
            m = str(mount).strip()
            if m:
                all_mounts.append(m)

        # Deduplicate by container path, preserving order
        deduplicated = deduplicate_mounts(all_mounts)

        # Build mount arguments with -v flags
        extra_mount_args: list[str] = []
        for mount in deduplicated:
            extra_mount_args.extend(["-v", mount])

        return extra_mount_args

    def _build_docker_run_args(
        self,
        platform_args: list[str],
        port_args: list[str],
        extra_mount_args: list[str],
        preflight_mounts: list[str],
        env_args: list[str],
        preflight_clause: str,
        agent_cmd: str,
    ) -> list[str]:
        """Build complete Docker run command arguments."""
        return [
            "run",
            *platform_args,
            "-d",
            "-t",
            "--name",
            self._runtime_env.container_name,
            *extra_mount_args,
            *preflight_mounts,
            *env_args,
            *port_args,
            "-w",
            self._runtime_env.container_cwd,
            self._runtime_env.runtime_image,
            "/bin/bash",
            "-lc",
            "set -euo pipefail; "
            f"{git_identity_clause()}"
            f"{preflight_clause}"
            f"{verify_cli_clause(self._runtime_env.agent_cli)}"
            f"exec {agent_cmd}",
        ]

    def _setup_desktop_port_mapping(
        self, desktop_state: dict[str, Any], docker_env: dict[str, str] | None
    ) -> None:
        """Setup desktop port mapping and noVNC URL."""
        try:
            mapping = _run_docker(
                ["port", self._container_id, "6080/tcp"], timeout_s=10.0, env=docker_env
            )
            first = (
                (mapping or "").strip().splitlines()[0]
                if (mapping or "").strip()
                else ""
            )
            host_port = first.rsplit(":", 1)[-1].strip() if ":" in first else ""
            if host_port.isdigit():
                desktop_state["NoVncUrl"] = f"http://127.0.0.1:{host_port}/vnc.html"
                self._on_log(
                    format_log(
                        "desktop",
                        "vnc",
                        "INFO",
                        f"noVNC URL: {desktop_state['NoVncUrl']}",
                    )
                )
        except Exception as exc:
            self._on_log(format_log("desktop", "vnc", "ERROR", str(exc)))

    def _report_state(self, desktop_state: dict[str, Any]) -> None:
        """Report current container state.

        Note: In unified runner flow, container is stopped/removed after execution,
        so state inspection may not be available. This method is kept for
        compatibility but may not provide meaningful state data.
        """
        if not self._container_id:
            return

        try:
            state = _inspect_state(self._container_id)
            if desktop_state:
                state = dict(state)
                state.update(desktop_state)
            self._on_state(state)
        except Exception:
            # Container may already be removed by unified runner
            pass

    def _monitor_container(self, desktop_state: dict[str, Any]) -> int:
        """Monitor container execution and stream logs. Returns exit code."""
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
                # Poll container state every 0.75 seconds
                if now - last_poll >= 0.75:
                    last_poll = now
                    try:
                        state = _inspect_state(self._container_id)
                        if state:
                            if desktop_state:
                                state = dict(state)
                                state.update(desktop_state)
                            self._on_state(state)
                            if (state.get("Status") or "").lower() in {
                                "exited",
                                "dead",
                            }:
                                break
                    except Exception:
                        pass

                # Check if logs process is still running
                if logs_proc.poll() is not None:
                    time.sleep(0.05)
                    continue

                # Read log output
                for key, _ in selector.select(timeout=0.05):
                    try:
                        chunk = key.fileobj.readline()
                        if chunk:
                            stream = (
                                "stdout"
                                if key.fileobj == logs_proc.stdout
                                else "stderr"
                            )
                            self._on_log(
                                wrap_container_log(
                                    self._container_id, stream, chunk.rstrip("\n")
                                )
                            )
                    except Exception:
                        pass
        finally:
            if logs_proc.poll() is None:
                logs_proc.terminate()
                try:
                    logs_proc.wait(timeout=2.0)
                except subprocess.TimeoutExpired:
                    logs_proc.kill()

        # Get final state and exit code
        try:
            final_state = _inspect_state(self._container_id)
            if desktop_state and final_state:
                final_state = dict(final_state)
                final_state.update(desktop_state)
            self._on_state(final_state)
            return int(final_state.get("ExitCode") or 0)
        except Exception:
            return 1

    def _cleanup_container(self) -> None:
        """Cleanup container if auto-remove is enabled."""
        try:
            _run_docker(["rm", "-f", self._container_id], timeout_s=30.0)
        except Exception:
            pass
