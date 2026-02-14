"""Container execution logic for Docker agent workers.

Handles Docker container orchestration including:
- Agent command building
- Desktop/VNC setup (cached and runtime variants)
- Preflight script execution
- Environment variable forwarding
- Container lifecycle management
- Log streaming and state monitoring

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
import shlex
import time
import selectors
import subprocess
from pathlib import Path
from typing import Any, Callable

from agents_runner.agent_cli import build_noninteractive_cmd, verify_cli_clause
from agents_runner.agent_cli import agent_requires_github_token
from agents_runner.github_token import resolve_github_token
from agents_runner.log_format import format_log, wrap_container_log
from agents_runner.core.shell_templates import git_identity_clause, shell_log_statement

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
    """Check if any cross-agent allowlisted agent requires a GitHub token."""
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
        if agent_cli and agent_requires_github_token(normalize_agent(agent_cli)):
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
        """Execute the agent container and return exit code.

        Returns:
            Container exit code (0 for success, non-zero for failure)
        """
        try:
            # Build agent command
            agent_args = self._build_agent_command()
            agent_cmd = " ".join(shlex.quote(part) for part in agent_args)

            # Setup desktop state tracking
            desktop_state: dict[str, Any] = {}

            # Build preflight clause and mounts
            preflight_clause, preflight_mounts = self._build_preflight_clause(
                desktop_state
            )

            # Build environment variables
            env_args, docker_env = self._build_env_args()

            # Build port args
            port_args = self._build_port_args()

            # Build extra mounts
            extra_mount_args = self._build_extra_mounts()

            # Build Docker run args
            args = self._build_docker_run_args(
                platform_args=self._runtime_env.platform_args,
                port_args=port_args,
                extra_mount_args=extra_mount_args,
                preflight_mounts=preflight_mounts,
                env_args=env_args,
                preflight_clause=preflight_clause,
                agent_cmd=agent_cmd,
            )

            # Start container
            self._container_id = _run_docker(args, timeout_s=60.0, env=docker_env)

            # Setup desktop port mapping if enabled
            if self._runtime_env.desktop_enabled and self._container_id:
                self._setup_desktop_port_mapping(desktop_state, docker_env)

            # Report initial state
            self._report_state(desktop_state)

            # Stream logs and monitor state
            exit_code = self._monitor_container(desktop_state)

            # Cleanup container if auto-remove enabled
            if self._config.auto_remove:
                self._cleanup_container()

            return exit_code

        except Exception as exc:
            self._on_log(format_log("docker", "container", "ERROR", str(exc)))
            return 1

    def _build_agent_command(self) -> list[str]:
        """Build the agent CLI command."""
        return build_noninteractive_cmd(
            agent=self._runtime_env.agent_cli,
            prompt=self._runtime_env.prompt_for_agent,
            host_workdir=self._runtime_env.host_mount,
            host_config_dir=self._config.host_config_dir,
            container_workdir=self._config.container_workdir,
            agent_cli_args=list(self._config.agent_cli_args or []),
        )

    def _build_preflight_clause(
        self, desktop_state: dict[str, Any]
    ) -> tuple[str, list[str]]:
        """Build preflight clause and mounts. Returns (clause, mounts)."""
        preflight_clause = ""
        preflight_mounts: list[str] = []

        # System preflight
        if (
            self._runtime_env.system_preflight_enabled
            and not self._runtime_env.system_preflight_cached
        ):
            clause, mounts = self._build_system_preflight()
            preflight_clause += clause
            preflight_mounts.extend(mounts)

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
        if (
            self._runtime_env.settings_preflight_tmp_path is not None
            and not self._runtime_env.settings_preflight_cached
        ):
            clause, mounts = self._build_settings_preflight(
                self._runtime_env.settings_preflight_tmp_path,
                self._runtime_env.settings_container_path,
            )
            preflight_clause += clause
            preflight_mounts.extend(mounts)

        # Environment preflight
        if (
            self._runtime_env.environment_preflight_tmp_path is not None
            and not self._runtime_env.environment_preflight_cached
        ):
            clause, mounts = self._build_environment_preflight(
                self._runtime_env.environment_preflight_tmp_path,
                self._runtime_env.environment_container_path,
            )
            preflight_clause += clause
            preflight_mounts.extend(mounts)

        return preflight_clause, preflight_mounts

    def _build_system_preflight(self) -> tuple[str, list[str]]:
        """Build system preflight clause and mounts."""
        host_preflights_dir = Path(self._runtime_env.preflights_host_dir).resolve()
        if not host_preflights_dir.is_dir():
            self._on_log(
                format_log(
                    "docker",
                    "preflight",
                    "WARN",
                    f"system preflight skipped; preflights dir not found: {host_preflights_dir}",
                )
            )
            return "", []
        container_dir = "/tmp/agents-runner-preflights"
        return (
            f"PREFLIGHTS_DIR={shlex.quote(container_dir)}; "
            'export AGENTS_RUNNER_PREFLIGHTS_DIR="${PREFLIGHTS_DIR}"; '
            'PREFLIGHT_SYSTEM="${PREFLIGHTS_DIR}/pixelarch_yay.sh"; '
            f"{shell_log_statement('docker', 'preflight', 'INFO', 'system: starting')}; "
            '/bin/bash "${PREFLIGHT_SYSTEM}"; '
            f"{shell_log_statement('docker', 'preflight', 'INFO', 'system: done')}; ",
            ["-v", f"{host_preflights_dir}:{container_dir}:ro"],
        )

    def _build_desktop_preflight_clause(self) -> str:
        """Build desktop preflight clause based on cached vs runtime setup."""
        using_cached_image = bool(self._runtime_env.desktop_cached)
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
        env_args.extend(["-e", "MIDORI_AI_AGENTS_RUNNER_INTERACTIVE=false"])

        # Forward GitHub tokens if needed
        needs_token = (
            _is_gh_context_enabled(self._config.environment_id)
            or agent_requires_github_token(self._runtime_env.agent_cli)
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
        for port_spec in self._config.ports or []:
            spec = str(port_spec or "").strip()
            if not spec:
                continue
            if self._runtime_env.desktop_enabled and self._publishes_container_port(
                spec, 6080
            ):
                continue
            port_args.extend(["-p", spec])
        if self._runtime_env.desktop_enabled:
            port_args.extend(["-p", "127.0.0.1::6080"])
        return port_args

    @staticmethod
    def _publishes_container_port(spec: str, port: int) -> bool:
        base = str(spec or "").strip()
        if not base:
            return False
        base = base.split("/", 1)[0]
        container_part = base.rsplit(":", 1)[-1].strip()
        if not container_part:
            return False
        if container_part.isdigit():
            return int(container_part) == int(port)
        if "-" in container_part:
            left, right = (p.strip() for p in container_part.split("-", 1))
            if left.isdigit() and right.isdigit():
                start = int(left)
                end = int(right)
                p = int(port)
                return start <= p <= end
        return False

    def _build_extra_mounts(self) -> list[str]:
        """Build extra mount arguments with deduplication."""
        # Collect all mount strings first (without -v flags)
        all_mounts: list[str] = []

        # Add primary config mount
        all_mounts.append(
            f"{self._config.host_config_dir}:{self._runtime_env.config_container_dir}"
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
        """Report current container state."""
        try:
            state = _inspect_state(self._container_id)
            if desktop_state:
                state = dict(state)
                state.update(desktop_state)
            self._on_state(state)
        except Exception:
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
