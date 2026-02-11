"""Worker setup logic for agent runtime environment preparation.

Handles platform detection, workspace resolution, template detection,
image preparation, and prompt assembly for Docker agent workers.
"""

import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Any

from agents_runner.prompt_sanitizer import sanitize_prompt
from agents_runner.agent_cli import (
    additional_config_mounts,
    container_config_dir,
    normalize_agent,
)
from agents_runner.docker.agent_worker_prompt import PromptAssembler
from agents_runner.docker_platform import (
    ROSETTA_INSTALL_COMMAND,
    docker_platform_args_for_pixelarch,
    docker_platform_for_pixelarch,
    has_rosetta,
)
from agents_runner.environments import load_environments
from agents_runner.docker.config import DockerRunnerConfig
from agents_runner.docker.process import _has_image, _has_platform_image, _pull_image
from agents_runner.docker.utils import _write_preflight_script
from agents_runner.docker.image_builder import (
    ensure_desktop_image,
    compute_desktop_cache_key,
)
from agents_runner.docker.env_image_builder import ensure_env_image
from agents_runner.log_format import format_log
from agents_runner.midoriai_template import (
    MidoriAITemplateDetection,
    scan_midoriai_agents_template,
)


@dataclass(frozen=True)
class RuntimeEnvironment:
    """Container runtime environment configuration."""

    forced_platform: str | None
    platform_args: list[str]
    rosetta_available: bool
    host_mount: str
    container_cwd: str
    config_container_dir: str
    config_extra_mounts: list[str]
    template_detection: MidoriAITemplateDetection
    container_name: str
    task_token: str
    artifacts_staging_dir: Path
    settings_container_path: str
    environment_container_path: str
    settings_preflight_tmp_path: str | None
    environment_preflight_tmp_path: str | None
    runtime_image: str
    desktop_enabled: bool
    desktop_cached: bool
    desktop_cache_key: str | None
    desktop_display: str
    container_caching_enabled: bool
    agent_cli: str
    prompt_for_agent: str


class WorkerSetup:
    """Handles runtime environment setup for Docker agent workers."""

    def __init__(
        self,
        config: DockerRunnerConfig,
        prompt: str,
        on_log: Callable[[str], None],
        on_state: Callable[[dict[str, Any]], None],
    ) -> None:
        self._config = config
        self._prompt = sanitize_prompt((prompt or "").strip())
        self._on_log = on_log
        self._on_state = on_state

    def prepare_runtime_environment(
        self, preflight_tmp_paths: list[str]
    ) -> RuntimeEnvironment:
        """Prepare the complete runtime environment."""
        platform_config = self._setup_platform()
        workspace_config = self._resolve_workspace(platform_config.agent_cli)
        template_detection = self._detect_and_persist_template(
            workspace_config.host_mount
        )
        artifacts_staging_dir = self._create_artifacts_directory()
        preflight_config = self._prepare_preflight_scripts(preflight_tmp_paths)
        self._pull_image_if_needed(
            platform_config.forced_platform, platform_config.platform_args
        )
        caching_config = self._setup_caching()

        # Assemble final prompt
        prompt_assembler = PromptAssembler(
            self._prompt, self._config.environment_id, self._on_log
        )
        final_prompt = prompt_assembler.assemble_prompt(
            platform_config.agent_cli,
            template_detection,
            caching_config.desktop_enabled,
            caching_config.desktop_display,
        )

        return RuntimeEnvironment(
            forced_platform=platform_config.forced_platform,
            platform_args=platform_config.platform_args,
            rosetta_available=platform_config.rosetta_available,
            host_mount=workspace_config.host_mount,
            container_cwd=workspace_config.container_cwd,
            config_container_dir=workspace_config.config_container_dir,
            config_extra_mounts=workspace_config.config_extra_mounts,
            template_detection=template_detection,
            container_name=(
                self._config.container_name
                if self._config.container_name
                else f"agents-runner-{uuid.uuid4().hex[:10]}"
            ),
            task_token=self._config.task_id or "task",
            artifacts_staging_dir=artifacts_staging_dir,
            settings_container_path=preflight_config.settings_container_path,
            environment_container_path=preflight_config.environment_container_path,
            settings_preflight_tmp_path=preflight_config.settings_preflight_tmp_path,
            environment_preflight_tmp_path=preflight_config.environment_preflight_tmp_path,
            runtime_image=caching_config.runtime_image,
            desktop_enabled=caching_config.desktop_enabled,
            desktop_cached=caching_config.desktop_cached,
            desktop_cache_key=caching_config.desktop_cache_key,
            desktop_display=caching_config.desktop_display,
            container_caching_enabled=caching_config.container_caching_enabled,
            agent_cli=platform_config.agent_cli,
            prompt_for_agent=final_prompt,
        )

    @dataclass(frozen=True)
    class _PlatformConfig:
        forced_platform: str | None
        platform_args: list[str]
        rosetta_available: bool
        agent_cli: str

    def _setup_platform(self) -> _PlatformConfig:
        """Setup platform-specific configuration."""
        os.makedirs(self._config.host_config_dir, exist_ok=True)
        forced_platform = docker_platform_for_pixelarch()
        platform_args = docker_platform_args_for_pixelarch()
        rosetta_available = True

        if forced_platform:
            self._on_log(
                format_log(
                    "host",
                    "none",
                    "INFO",
                    f"forcing Docker platform: {forced_platform}",
                )
            )
            rosetta_available = has_rosetta()
            if not rosetta_available:
                self._on_log(
                    format_log(
                        "host",
                        "none",
                        "WARN",
                        f"Rosetta 2 not detected; install with: {ROSETTA_INSTALL_COMMAND}",
                    )
                )

        # Don't normalize test/debug commands - pass them through as-is
        agent_cli_raw = str(self._config.agent_cli or "").strip().lower()
        if agent_cli_raw in (
            "echo",
            "sh",
            "bash",
            "true",
            "false",
            "/bin/sh",
            "/bin/bash",
            "/usr/bin/sh",
            "/usr/bin/bash",
        ):
            agent_cli = agent_cli_raw
        else:
            agent_cli = normalize_agent(self._config.agent_cli)

        return self._PlatformConfig(
            forced_platform=forced_platform,
            platform_args=platform_args,
            rosetta_available=rosetta_available,
            agent_cli=agent_cli,
        )

    @dataclass(frozen=True)
    class _WorkspaceConfig:
        host_mount: str
        container_cwd: str
        config_container_dir: str
        config_extra_mounts: list[str]

    def _resolve_workspace(self, agent_cli: str) -> _WorkspaceConfig:
        """Resolve workspace mount points."""
        host_mount = os.path.abspath(
            os.path.expanduser(str(self._config.host_workdir or "").strip())
        )
        container_cwd = (
            str(self._config.container_workdir or "").strip()
            or "/home/midori-ai/workspace"
        )

        return self._WorkspaceConfig(
            host_mount=host_mount,
            container_cwd=container_cwd,
            config_container_dir=(
                str(self._config.container_config_dir or "").strip()
                or container_config_dir(agent_cli)
            ),
            config_extra_mounts=additional_config_mounts(
                agent_cli, self._config.host_config_dir
            ),
        )

    def _detect_and_persist_template(
        self, host_mount: str
    ) -> MidoriAITemplateDetection:
        """Detect and persist Midori AI template."""
        template_detection = scan_midoriai_agents_template(host_mount)

        if self._config.environment_id:
            try:
                from agents_runner.environments import save_environment

                env = load_environments().get(str(self._config.environment_id))
                if env is not None:
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
                    "Midori AI Agents Template detected; will inject template prompts",
                )
            )

        return template_detection

    def _create_artifacts_directory(self) -> Path:
        """Create artifacts staging directory."""
        artifacts_staging_dir = (
            Path.home()
            / ".midoriai"
            / "agents-runner"
            / "artifacts"
            / (self._config.task_id or "task")
            / "staging"
        )
        artifacts_staging_dir.mkdir(parents=True, exist_ok=True)
        self._on_log(
            format_log(
                "host", "none", "INFO", f"artifacts staging: {artifacts_staging_dir}"
            )
        )
        return artifacts_staging_dir

    @dataclass(frozen=True)
    class _PreflightConfig:
        settings_container_path: str
        environment_container_path: str
        settings_preflight_tmp_path: str | None
        environment_preflight_tmp_path: str | None

    def _prepare_preflight_scripts(
        self, preflight_tmp_paths: list[str]
    ) -> _PreflightConfig:
        """Prepare preflight scripts."""
        task_token = self._config.task_id or "task"
        settings_preflight_tmp_path = None
        environment_preflight_tmp_path = None

        if (self._config.settings_preflight_script or "").strip():
            settings_preflight_tmp_path = _write_preflight_script(
                str(self._config.settings_preflight_script),
                "settings",
                self._config.task_id,
                preflight_tmp_paths,
            )
        if (self._config.environment_preflight_script or "").strip():
            environment_preflight_tmp_path = _write_preflight_script(
                str(self._config.environment_preflight_script),
                "environment",
                self._config.task_id,
                preflight_tmp_paths,
            )

        return self._PreflightConfig(
            settings_container_path=self._config.container_settings_preflight_path.replace(
                "{task_id}", task_token
            ),
            environment_container_path=self._config.container_environment_preflight_path.replace(
                "{task_id}", task_token
            ),
            settings_preflight_tmp_path=settings_preflight_tmp_path,
            environment_preflight_tmp_path=environment_preflight_tmp_path,
        )

    def _pull_image_if_needed(
        self, forced_platform: str | None, platform_args: list[str]
    ) -> None:
        """Pull Docker image if needed."""
        should_pull = (
            self._config.pull_before_run
            or (
                forced_platform
                and not _has_platform_image(self._config.image, forced_platform)
            )
            or (not forced_platform and not _has_image(self._config.image))
        )

        if should_pull:
            self._on_state({"Status": "pulling"})
            msg = (
                f"docker pull {self._config.image}"
                if self._config.pull_before_run
                else f"image missing; docker pull {self._config.image}"
            )
            self._on_log(format_log("host", "none", "INFO", msg))
            _pull_image(self._config.image, platform_args=platform_args)
            self._on_log(format_log("host", "none", "INFO", "pull complete"))

    @dataclass(frozen=True)
    class _CachingConfig:
        runtime_image: str
        desktop_enabled: bool
        desktop_cached: bool
        desktop_cache_key: str | None
        desktop_display: str
        container_caching_enabled: bool

    def _setup_caching(self) -> _CachingConfig:
        """Setup desktop and environment caching."""
        runtime_image = self._config.image
        desktop_enabled = bool(self._config.headless_desktop_enabled)
        desktop_cached = bool(self._config.desktop_cache_enabled)
        desktop_cache_key: str | None = None

        if desktop_enabled and desktop_cached:
            self._on_log(
                format_log(
                    "desktop",
                    "setup",
                    "INFO",
                    "cache enabled; checking for cached image",
                )
            )
            try:
                runtime_image = ensure_desktop_image(
                    self._config.image, on_log=self._on_log
                )
                if runtime_image != self._config.image:
                    self._on_log(
                        format_log(
                            "desktop",
                            "setup",
                            "INFO",
                            f"using cached image: {runtime_image}",
                        )
                    )
                    desktop_cache_key = compute_desktop_cache_key(self._config.image)
                else:
                    self._on_log(
                        format_log(
                            "desktop",
                            "setup",
                            "WARN",
                            "cache build failed; falling back to runtime install",
                        )
                    )
            except Exception as exc:
                self._on_log(
                    format_log(
                        "desktop",
                        "setup",
                        "ERROR",
                        f"cache error: {exc}; falling back to runtime install",
                    )
                )
                runtime_image = self._config.image

        container_caching_enabled = bool(self._config.container_caching_enabled)
        cached_preflight_script = (self._config.cached_preflight_script or "").strip()

        if container_caching_enabled and cached_preflight_script:
            self._on_log(
                format_log(
                    "env",
                    "cache",
                    "INFO",
                    "container caching enabled; checking for cached image",
                )
            )
            try:
                runtime_image = ensure_env_image(
                    self._config.image,
                    desktop_cache_key,
                    cached_preflight_script,
                    on_log=self._on_log,
                )
                if runtime_image.startswith("agent-runner-env:"):
                    self._on_log(
                        format_log(
                            "env",
                            "cache",
                            "INFO",
                            f"using cached environment image: {runtime_image}",
                        )
                    )
                else:
                    self._on_log(
                        format_log(
                            "env",
                            "cache",
                            "WARN",
                            "cache build failed; falling back to runtime preflight",
                        )
                    )
            except Exception as exc:
                self._on_log(
                    format_log(
                        "env",
                        "cache",
                        "ERROR",
                        f"error: {exc}; falling back to runtime preflight",
                    )
                )
        elif container_caching_enabled and not cached_preflight_script:
            self._on_log(
                format_log(
                    "env",
                    "cache",
                    "WARN",
                    "container caching enabled but no cached preflight script configured",
                )
            )

        return self._CachingConfig(
            runtime_image=runtime_image,
            desktop_enabled=desktop_enabled,
            desktop_cached=desktop_cached,
            desktop_cache_key=desktop_cache_key,
            desktop_display=":1",
            container_caching_enabled=container_caching_enabled,
        )
