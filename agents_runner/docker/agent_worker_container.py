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

import shlex
from pathlib import Path
from typing import Any, Callable

from agents_runner.agent_cli import normalize_agent, verify_cli_clause
from agents_runner.agent_systems import requires_github_token
from agents_runner.github_token import resolve_github_token
from agents_runner.log_format import format_log
from agents_runner.core.shell_templates import git_identity_clause, shell_log_statement
from agents_runner.planner import (
    EnvironmentSpec,
    RunRequest,
    SubprocessDockerAdapter,
    execute_plan,
    plan_run,
)

from agents_runner.docker.config import DockerRunnerConfig
from agents_runner.docker.process import _inspect_state
from agents_runner.docker.agent_worker_setup import RuntimeEnvironment
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
    """Check if any cross-agent requires GitHub token."""
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

    agent_cli_by_id: dict[str, str] = {
        agent.agent_id: agent.agent_cli for agent in env.agent_selection.agents
    }

    for agent_id in env.cross_agent_allowlist:
        agent_cli = agent_cli_by_id.get(agent_id)
        if agent_cli and requires_github_token(normalize_agent(agent_cli)):
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

            # Setup desktop state tracking
            desktop_state: dict[str, Any] = {}

            # Build preflight clause for injection into plan
            preflight_clause, preflight_mounts = self._build_preflight_clause(
                desktop_state
            )

            # Build RunRequest for planner
            request = self._build_run_request(preflight_mounts)

            # Call planner to get RunPlan
            plan = plan_run(request)

            # Inject preflight logic into exec command if needed
            if preflight_clause:
                plan = self._inject_preflight_into_plan(plan, preflight_clause)

            # Execute plan using unified runner
            self._on_log(format_log("docker", "runner", "INFO", "starting container"))
            adapter = SubprocessDockerAdapter()
            result = execute_plan(plan, adapter)

            # Store container ID from execution result
            self._container_id = result.container_id or plan.docker.container_name

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

    def _build_run_request(self, preflight_mounts: list[str]) -> RunRequest:
        """Build a RunRequest for the planner.

        Args:
            preflight_mounts: Additional mount strings for preflight scripts

        Returns:
            RunRequest ready for planning
        """
        # Build EnvironmentSpec from runtime environment
        env_spec = EnvironmentSpec(
            env_id=self._config.environment_id or "default",
            image=self._runtime_env.runtime_image,
            env_vars=self._build_env_dict(),
            extra_mounts=self._build_extra_mount_strings(preflight_mounts),
        )

        # Build RunRequest
        return RunRequest(
            interactive=False,
            system_name=self._runtime_env.agent_cli,
            prompt=self._runtime_env.prompt_for_agent,
            environment=env_spec,
            host_workdir=Path(self._runtime_env.host_mount),
            host_config_dir=Path(self._config.host_codex_dir),
            extra_cli_args=list(self._config.agent_cli_args or []),
        )

    def _build_extra_mount_strings(self, preflight_mounts: list[str]) -> list[str]:
        """Build list of extra mount strings for EnvironmentSpec.

        Args:
            preflight_mounts: Additional mount strings for preflight scripts

        Returns:
            List of mount strings in "src:dst:mode" format
        """
        mount_strings: list[str] = []

        # Add artifacts mount
        mount_strings.append(
            f"{self._runtime_env.artifacts_staging_dir}:/tmp/agents-artifacts:rw"
        )

        # Add extra mounts from config
        for mount in self._config.extra_mounts or []:
            m = str(mount).strip()
            if m:
                mount_strings.append(m)

        # Add config extra mounts (cross-agent configs, etc.)
        for mount in self._runtime_env.config_extra_mounts:
            m = str(mount).strip()
            if m:
                mount_strings.append(m)

        # Add preflight mounts (convert from -v flag format)
        i = 0
        while i < len(preflight_mounts):
            if preflight_mounts[i] == "-v" and i + 1 < len(preflight_mounts):
                mount_strings.append(preflight_mounts[i + 1])
                i += 2
            else:
                i += 1

        return mount_strings

    def _inject_preflight_into_plan(self, plan, preflight_clause: str):
        """Inject preflight logic into the plan's exec command.

        The planner builds a command using build_noninteractive_cmd, but we need
        to wrap it with bash and inject preflight setup. This modifies the plan
        to include the preflight logic.

        Args:
            plan: The RunPlan from the planner
            preflight_clause: Bash commands for preflight setup

        Returns:
            Modified RunPlan with preflight logic injected
        """

        # Extract the agent command from the exec spec
        agent_cmd = " ".join(shlex.quote(part) for part in plan.exec_spec.argv)

        # Build complete bash command with preflight
        bash_cmd = (
            "set -euo pipefail; "
            f"{git_identity_clause()}"
            f"{preflight_clause}"
            f"{verify_cli_clause(self._runtime_env.agent_cli)}"
            f"exec {agent_cmd}"
        )

        # Create a new exec spec with the wrapped command
        from agents_runner.planner.models import ExecSpec

        new_exec_spec = ExecSpec(
            argv=["/bin/bash", "-lc", bash_cmd],
            cwd=plan.exec_spec.cwd,
            env=plan.exec_spec.env,
            tty=plan.exec_spec.tty,
            stdin=plan.exec_spec.stdin,
        )

        # Create a new plan with the modified exec spec
        from agents_runner.planner.models import RunPlan

        return RunPlan(
            interactive=plan.interactive,
            docker=plan.docker,
            prompt_text=plan.prompt_text,
            exec_spec=new_exec_spec,
            artifacts=plan.artifacts,
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
            or requires_github_token(self._runtime_env.agent_cli)
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
