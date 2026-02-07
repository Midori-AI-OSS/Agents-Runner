"""Pydantic models for run planning and execution.

These models represent the data structures used to plan and execute agent runs
in Docker containers. They are headless (no Qt/UI dependencies) and form the
core contract between the planner, runner, and UI subsystems.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class MountSpec(BaseModel):
    """Specification for a Docker volume mount.

    Attributes:
        src: Source path on the host (must be absolute).
        dst: Destination path in the container (must be absolute).
        mode: Mount mode, either read-only ("ro") or read-write ("rw").
    """

    src: Path
    dst: Path
    mode: Literal["ro", "rw"] = "rw"

    @field_validator("src", "dst")
    @classmethod
    def validate_absolute_path(cls, v: Path) -> Path:
        """Ensure mount paths are absolute."""
        if not v.is_absolute():
            raise ValueError(f"Mount path must be absolute: {v}")
        return v


class TimeoutSpec(BaseModel):
    """Timeout configuration for different run phases.

    Attributes:
        pull_seconds: Maximum time to wait for image pull (default: 15 minutes).
        ready_seconds: Maximum time to wait for container readiness (default: 5 minutes).
        run_seconds: Maximum time to wait for run completion (None = no limit).
    """

    pull_seconds: int = 60 * 15
    ready_seconds: int = 60 * 5
    run_seconds: int | None = None


class DockerSpec(BaseModel):
    """Docker container configuration.

    Attributes:
        image: Docker image reference (e.g., "python:3.13").
        container_name: Optional container name (auto-generated if None).
        workdir: Working directory inside the container.
        mounts: List of volume mounts to attach.
        env: Environment variables to set in the container.
        keepalive_argv: Command to keep container running (default: ["sleep", "infinity"]).
        ports: List of port mappings (e.g., ["127.0.0.1::6080"] for desktop/VNC).
    """

    image: str
    container_name: str | None = None
    workdir: Path = Path("/workspace")
    mounts: list[MountSpec] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    keepalive_argv: list[str] = Field(default_factory=lambda: ["sleep", "infinity"])
    ports: list[str] = Field(default_factory=list)

    @field_validator("workdir")
    @classmethod
    def validate_absolute_workdir(cls, v: Path) -> Path:
        """Ensure workdir is absolute."""
        if not v.is_absolute():
            raise ValueError(f"Workdir must be absolute: {v}")
        return v


class ExecSpec(BaseModel):
    """Specification for a docker exec command.

    Attributes:
        argv: Command and arguments to execute.
        cwd: Working directory for the command (None = use container workdir).
        env: Additional environment variables for this exec.
        tty: Whether to allocate a pseudo-TTY.
        stdin: Whether to keep stdin open.
    """

    argv: list[str]
    cwd: Path | None = None
    env: dict[str, str] = Field(default_factory=dict)
    tty: bool = False
    stdin: bool = False

    @field_validator("cwd")
    @classmethod
    def validate_absolute_cwd(cls, v: Path | None) -> Path | None:
        """Ensure cwd is absolute if provided."""
        if v is not None and not v.is_absolute():
            raise ValueError(f"Exec cwd must be absolute: {v}")
        return v


class ArtifactSpec(BaseModel):
    """Artifact collection configuration.

    Attributes:
        finish_file: Path to a finish marker file (None = no marker).
        output_file: Path to an output file to collect (None = no output).
    """

    finish_file: Path | None = None
    output_file: Path | None = None


class EnvironmentSpec(BaseModel):
    """Runtime environment specification.

    This model represents the environment settings used by the planner to
    construct a RunPlan. It is derived from stored environment models.

    Attributes:
        env_id: Unique identifier for this environment.
        image: Docker image to use.
        env_vars: Environment variables to forward into the container.
        extra_mounts: Additional mount paths (as strings, parsed by planner).
        settings_preflight_script: Optional script to run before starting.
        environment_preflight_script: Optional environment setup script.
        headless_desktop_enabled: Whether to enable headless desktop (Xvfb).
        desktop_cache_enabled: Whether to cache desktop state.
        container_caching_enabled: Whether to reuse containers between runs.
        gh_context_enabled: Whether to forward GitHub context.
        use_cross_agents: Whether to enable cross-agent features.
    """

    env_id: str
    image: str
    env_vars: dict[str, str] = Field(default_factory=dict)
    extra_mounts: list[str] = Field(default_factory=list)
    settings_preflight_script: str | None = None
    environment_preflight_script: str | None = None
    headless_desktop_enabled: bool = False
    desktop_cache_enabled: bool = False
    container_caching_enabled: bool = False
    gh_context_enabled: bool = False
    use_cross_agents: bool = False


class RunRequest(BaseModel):
    """User intent for an agent run.

    This model captures what the user wants to run, before any resolution
    or planning has occurred. The planner converts this into a RunPlan.

    Attributes:
        interactive: Whether this is an interactive run (default: False).
        system_name: Name of the agent system to use (e.g., "codex", "claude").
        prompt: User prompt/instruction for the agent.
        environment: Environment specification to use.
        host_workdir: Host workspace directory (must be absolute).
        host_config_dir: Host configuration directory (must be absolute).
        extra_cli_args: Additional CLI arguments to pass to the agent.
        timeouts: Timeout configuration for this run.
    """

    interactive: bool = False
    system_name: str
    prompt: str
    environment: EnvironmentSpec
    host_workdir: Path
    host_config_dir: Path
    extra_cli_args: list[str] = Field(default_factory=list)
    timeouts: TimeoutSpec = Field(default_factory=TimeoutSpec)

    @field_validator("host_workdir", "host_config_dir")
    @classmethod
    def validate_absolute_host_path(cls, v: Path) -> Path:
        """Ensure host paths are absolute."""
        if not v.is_absolute():
            raise ValueError(f"Host path must be absolute: {v}")
        return v


class RunPlan(BaseModel):
    """Fully-resolved executable plan for an agent run.

    This model is the output of the planner and contains all the information
    needed by the docker runner to execute the run.

    Attributes:
        interactive: Whether this is an interactive run.
        docker: Docker container configuration.
        prompt_text: Composed prompt text to feed to the agent.
        exec_spec: Execution specification for the agent command.
        artifacts: Artifact collection specification.
    """

    interactive: bool
    docker: DockerSpec
    prompt_text: str
    exec_spec: ExecSpec
    artifacts: ArtifactSpec
