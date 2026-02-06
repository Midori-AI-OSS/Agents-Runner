"""Run-planning subsystem for agent execution.

This package provides Pydantic models for planning and executing agent runs
in a headless, framework-agnostic way. The planner converts RunRequest objects
into fully-resolved RunPlan objects that can be executed by the docker runner.
"""

from agents_runner.planner.docker_adapter import DockerAdapter, ExecutionResult
from agents_runner.planner.models import (
    ArtifactSpec,
    DockerSpec,
    EnvironmentSpec,
    ExecSpec,
    MountSpec,
    RunPlan,
    RunRequest,
    TimeoutSpec,
)
from agents_runner.planner.planner import plan_run
from agents_runner.planner.runner import execute_plan
from agents_runner.planner.subprocess_adapter import SubprocessDockerAdapter

__all__ = [
    "ArtifactSpec",
    "DockerAdapter",
    "DockerSpec",
    "EnvironmentSpec",
    "ExecSpec",
    "ExecutionResult",
    "MountSpec",
    "RunPlan",
    "RunRequest",
    "SubprocessDockerAdapter",
    "TimeoutSpec",
    "execute_plan",
    "plan_run",
]
