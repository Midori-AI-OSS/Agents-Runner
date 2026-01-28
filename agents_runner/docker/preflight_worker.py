import os
import time
import uuid
import shlex
import selectors
import subprocess

from typing import Any
from typing import Callable

from threading import Event

from agents_runner.agent_cli import additional_config_mounts
from agents_runner.agent_cli import container_config_dir
from agents_runner.agent_cli import normalize_agent
from agents_runner.docker_platform import ROSETTA_INSTALL_COMMAND
from agents_runner.docker_platform import docker_platform_args_for_pixelarch
from agents_runner.docker_platform import docker_platform_for_pixelarch
from agents_runner.docker_platform import has_rosetta
from agents_runner.gh_management import GhManagementError
from agents_runner.gh_management import prepare_github_repo_for_task
from agents_runner.github_token import resolve_github_token

from agents_runner.docker.config import DockerRunnerConfig
from agents_runner.docker.process import _has_image
from agents_runner.docker.process import _has_platform_image
from agents_runner.docker.process import _inspect_state
from agents_runner.docker.process import _pull_image
from agents_runner.docker.process import _run_docker
from agents_runner.docker.utils import _resolve_workspace_mount
from agents_runner.log_format import format_log
from agents_runner.log_format import wrap_container_log
from agents_runner.ui.shell_templates import git_identity_clause
from agents_runner.ui.shell_templates import shell_log_statement
from agents_runner.docker.utils import _write_preflight_script
from agents_runner.midoriai_template import MidoriAITemplateDetection
from agents_runner.midoriai_template import scan_midoriai_agents_template


def _needs_cross_agent_gh_token(environment_id: str | None) -> bool:
    """Check if copilot is in the cross-agent allowlist.
    
    Returns True if any agent in cross_agent_allowlist uses copilot CLI.
    """
    if not environment_id:
        return False
    
    # Load environment and validate structure
    try:
        from agents_runner.environments import load_environments
        environments = load_environments()
        env = environments.get(str(environment_id))
    except Exception:
        return False
    
    if env is None or not env.cross_agent_allowlist:
        return False
    
    if env.agent_selection is None or not env.agent_selection.agents:
        return False
    
    # Build agent_id → agent_cli mapping for quick lookup
    agent_cli_by_id: dict[str, str] = {
        agent.agent_id: agent.agent_cli
        for agent in env.agent_selection.agents
    }
    
    # Check each allowlisted agent_id for copilot
    for agent_id in env.cross_agent_allowlist:
        agent_cli = agent_cli_by_id.get(agent_id)
        if agent_cli and normalize_agent(agent_cli) == "copilot":
            return True
    
    return False


class DockerPreflightWorker:
    def __init__(
        self,
        config: DockerRunnerConfig,
        on_state: Callable[[dict[str, Any]], None],
        on_log: Callable[[str], None],
        on_done: Callable[[int, str | None], None],
    ) -> None:
        self._config = config
        self._on_state = on_state
        self._on_log = on_log
        self._on_done = on_done
        self._stop = Event()
        self._container_id: str | None = None

    @property
    def container_id(self) -> str | None:
        return self._container_id

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

    def request_kill(self) -> None:
        self._stop.set()
        if self._container_id:
            try:
                _run_docker(["kill", self._container_id], timeout_s=10.0)
            except Exception:
                pass

    def run(self) -> None:
        preflight_tmp_paths: list[str] = []
        docker_env: dict[str, str] | None = None
        try:
            # GitHub repo preparation (clone + update) - happens first, before Docker
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
                    if result.get("branch"):
                        self._on_log(format_log("gh", "repo", "INFO", f"ready on branch {result['branch']}"))
                except (GhManagementError, Exception) as exc:
                    self._on_log(format_log("gh", "repo", "ERROR", str(exc)))
                    self._on_done(1, str(exc))
                    return

            os.makedirs(self._config.host_codex_dir, exist_ok=True)
            forced_platform = docker_platform_for_pixelarch()
            platform_args = docker_platform_args_for_pixelarch()
            if forced_platform:
                self._on_log(format_log("host", "none", "INFO", f"forcing Docker platform: {forced_platform}"))
                rosetta = has_rosetta()
                if rosetta is False:
                    self._on_log(
                        format_log(
                            "host",
                            "none",
                            "WARN",
                            f"Rosetta 2 not detected; install with: {ROSETTA_INSTALL_COMMAND}",
                        )
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
                    format_log(
                        "host",
                        "none",
                        "INFO",
                        f"mounting workspace root: {host_mount} (selected {self._config.host_workdir})",
                    )
                )
            if container_cwd != self._config.container_workdir:
                self._on_log(format_log("host", "none", "INFO", f"container workdir: {container_cwd}"))

            template_detection = scan_midoriai_agents_template(host_mount)
            if self._config.environment_id:
                try:
                    from agents_runner.environments import load_environments
                    from agents_runner.environments import save_environment

                    env = load_environments().get(str(self._config.environment_id))
                    if env is not None:
                        # Only update template detection if not already set
                        # For cloned workspaces, we scan once and persist the result
                        if env.midoriai_template_likelihood == 0.0:
                            env.midoriai_template_likelihood = (
                                template_detection.midoriai_template_likelihood
                            )
                            env.midoriai_template_detected = (
                                template_detection.midoriai_template_detected
                            )
                            env.midoriai_template_detected_path = (
                                template_detection.midoriai_template_detected_path
                            )
                            save_environment(env)
                        else:
                            # Reuse saved template detection values
                            template_detection = MidoriAITemplateDetection(
                                midoriai_template_likelihood=env.midoriai_template_likelihood,
                                midoriai_template_detected=env.midoriai_template_detected,
                                midoriai_template_detected_path=env.midoriai_template_detected_path,
                            )
                except Exception as exc:
                    self._on_log(
                        format_log(
                            "env",
                            "template",
                            "WARN",
                            f"failed to persist template detection: {exc}",
                        )
                    )
            if template_detection.midoriai_template_detected:
                self._on_log(
                    format_log(
                        "env",
                        "template",
                        "INFO",
                        "Midori AI Agents Template detected (preflight)",
                    )
                )
            container_name = f"codex-preflight-{uuid.uuid4().hex[:10]}"
            task_token = self._config.task_id or "task"
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
                self._on_log(format_log("host", "none", "INFO", f"docker pull {self._config.image}"))
                _pull_image(self._config.image, platform_args=platform_args)
                self._on_log(format_log("host", "none", "INFO", "pull complete"))
            elif forced_platform and not _has_platform_image(
                self._config.image, forced_platform
            ):
                self._on_state({"Status": "pulling"})
                self._on_log(format_log("host", "none", "INFO", f"image missing; docker pull {self._config.image}"))
                _pull_image(self._config.image, platform_args=platform_args)
                self._on_log(format_log("host", "none", "INFO", "pull complete"))
            elif not forced_platform and not _has_image(self._config.image):
                self._on_state({"Status": "pulling"})
                self._on_log(format_log("host", "none", "INFO", f"image missing; docker pull {self._config.image}"))
                _pull_image(self._config.image, platform_args=platform_args)
                self._on_log(format_log("host", "none", "INFO", "pull complete"))

            preflight_clause = ""
            preflight_mounts: list[str] = []
            if settings_preflight_tmp_path is not None:
                self._on_log(
                    format_log(
                        "host",
                        "none",
                        "INFO",
                        f"settings preflight enabled; mounting -> {settings_container_path} (ro)",
                    )
                )
                preflight_mounts.extend(
                    [
                        "-v",
                        f"{settings_preflight_tmp_path}:{settings_container_path}:ro",
                    ]
                )
                preflight_clause += (
                    f"PREFLIGHT_SETTINGS={shlex.quote(settings_container_path)}; "
                    f'{shell_log_statement("env", "setup", "INFO", "settings: running")}; '
                    '/bin/bash "${PREFLIGHT_SETTINGS}"; '
                    f'{shell_log_statement("env", "setup", "INFO", "settings: done")}; '
                )

            if environment_preflight_tmp_path is not None:
                self._on_log(
                    format_log(
                        "host",
                        "none",
                        "INFO",
                        f"environment preflight enabled; mounting -> {environment_container_path} (ro)",
                    )
                )
                preflight_mounts.extend(
                    [
                        "-v",
                        f"{environment_preflight_tmp_path}:{environment_container_path}:ro",
                    ]
                )
                preflight_clause += (
                    f"PREFLIGHT_ENV={shlex.quote(environment_container_path)}; "
                    f'{shell_log_statement("env", "setup", "INFO", "environment: running")}; '
                    '/bin/bash "${PREFLIGHT_ENV}"; '
                    f'{shell_log_statement("env", "setup", "INFO", "environment: done")}; '
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
                    docker_env = dict(os.environ)
                    docker_env["GH_TOKEN"] = token
                    docker_env["GITHUB_TOKEN"] = token
                    env_args.extend(["-e", "GH_TOKEN", "-e", "GITHUB_TOKEN"])
            elif _needs_cross_agent_gh_token(self._config.environment_id) and agent_cli != "copilot":
                token = resolve_github_token()
                if (
                    token
                    and "GH_TOKEN" not in (self._config.env_vars or {})
                    and "GITHUB_TOKEN" not in (self._config.env_vars or {})
                ):
                    self._on_log(
                        format_log("docker", "auth", "INFO", "forwarding GitHub token for cross-agent copilot")
                    )
                    if docker_env is None:
                        docker_env = dict(os.environ)
                    docker_env["GH_TOKEN"] = token
                    docker_env["GITHUB_TOKEN"] = token
                    env_args.extend(["-e", "GH_TOKEN", "-e", "GITHUB_TOKEN"])

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
                *extra_mount_args,
                *preflight_mounts,
                *env_args,
                "-w",
                container_cwd,
                self._config.image,
                "/bin/bash",
                "-lc",
                "set -euo pipefail; "
                f"{git_identity_clause()}"
                f"{preflight_clause}"
                f'{shell_log_statement("docker", "preflight", "INFO", "complete")}; ',
            ]
            self._container_id = _run_docker(args, timeout_s=60.0, env=docker_env)
            try:
                self._on_state(_inspect_state(self._container_id))
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
                            stream = "stdout" if key.fileobj == logs_proc.stdout else "stderr"
                            self._on_log(wrap_container_log(self._container_id, stream, chunk.rstrip("\n")))
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
            self._on_state(final_state)
            exit_code = int(final_state.get("ExitCode") or 0)

            if self._config.auto_remove:
                try:
                    _run_docker(["rm", "-f", self._container_id], timeout_s=30.0)
                except Exception:
                    pass

            self._on_done(exit_code, None)
        except Exception as exc:
            self._on_done(1, str(exc))
        finally:
            for tmp_path in preflight_tmp_paths:
                try:
                    if os.path.exists(tmp_path):
                        os.unlink(tmp_path)
                except Exception:
                    pass
