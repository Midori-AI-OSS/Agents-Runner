# Unify run planning via Pydantic (`interactive=True`)

Issue
- Agent runs and Interactive runs assemble “what to run” via separate codepaths, which causes drift (image pull timing, mounts/preflights, desktop state, container polling).

Goal
- Standardize a single end-to-end flow for both task types, driven by a shared Pydantic data model.
- Make interactive vs non-interactive a boolean (`interactive=True`) and keep the rest of the run logic identical.
- Keep Qt/UI isolated under `agents_runner/ui/` (UI builds a request + renders state; core planning/running is headless).

Prompting (both task types)
- Always feed the composed prompt into the run (interactive and non-interactive).
- Interactive guardrail:
  - Prefix the user prompt with: `do not take action, just review the needed files and check your preflight if the repo has those and then standby`
- Copilot: interactive runs are not supported.
- Keep prompt composition in the planner so the UI path and CLI path cannot drift.

Proposed standardized flow (both task types)
1) Build `RunRequest` from UI/CLI inputs (agent, prompt, workspace, image, env, timeouts, `interactive`).
2) Convert to `RunPlan` (fully-resolved image ref, mounts, working dir, env, command, artifact paths, state transitions).
3) Ensure image is present (pull happens here, before any terminal window opens).
4) Start container in the background with a keepalive command (ex: `sleep infinity`), then run everything via `docker exec`.
5) Wait for readiness (after pull + after container start; no pinging before pull).
6) Run:
   - Non-interactive: `docker exec` the agent command and capture exit code/output.
   - Interactive: open terminal and attach via `docker exec -it ...` (UI concern).
7) Finalize (last step): copy/collect artifacts, stop container, remove container, update UI state.

Model sketch
- `RunRequest`: user intent + knobs (includes `interactive: bool`).
- `RunPlan`: resolved executable plan (image ref, container name, mounts/env, exec specs, artifact specs).
- `ExecSpec`: argv, cwd, env overlay, tty/stdin policy.
- `ArtifactSpec`: finish file path(s), output capture, optional docker cp rules.

Model prototype (Pydantic sketch)
```py
from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class MountSpec(BaseModel):
    src: Path
    dst: Path
    mode: Literal["ro", "rw"] = "rw"


class TimeoutSpec(BaseModel):
    pull_seconds: int = 60 * 15
    ready_seconds: int = 60 * 5
    run_seconds: int | None = None


class DockerSpec(BaseModel):
    image: str
    container_name: str | None = None
    workdir: Path = Path("/workspace")
    mounts: list[MountSpec] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    keepalive_argv: list[str] = Field(default_factory=lambda: ["sleep", "infinity"])


class ExecSpec(BaseModel):
    argv: list[str]
    cwd: Path | None = None
    env: dict[str, str] = Field(default_factory=dict)
    tty: bool = False
    stdin: bool = False


class ArtifactSpec(BaseModel):
    finish_file: Path | None = None
    output_file: Path | None = None


class RunRequest(BaseModel):
    interactive: bool = False
    prompt: str
    docker: DockerSpec
    exec_spec: ExecSpec
    timeouts: TimeoutSpec = Field(default_factory=TimeoutSpec)

    # policy: interactive Copilot runs are not supported


class RunPlan(BaseModel):
    interactive: bool
    docker: DockerSpec
    prompt_text: str
    exec_spec: ExecSpec
    artifacts: ArtifactSpec
```

Subtasks (small, reviewable)
- Add `pydantic` dependency and introduce models (`RunRequest`, `RunPlan`, specs) in a headless package.
- Implement a planner: `RunPlan = plan_run(RunRequest)`.
- Implement a docker runner that follows the standardized flow (pull → start keepalive container → readiness → exec → finalize).
- Add unit tests for `plan_run` and docker runner sequencing (fake docker adapter; no docker needed).
- Switch non-interactive task execution to the shared planner/runner.
- Switch interactive UI path to the shared planner/runner (UI only responsible for launching the terminal with `docker exec -it`).
- Remove duplicate per-mode “plan assembly” codepaths once callers are migrated.

Constraints
- Minimal diffs per subtask; avoid drive-by refactors.
- Keep boundaries explicit (no Qt imports outside `agents_runner/ui/`).

Testability
- Keep planning pure (no subprocess/filesystem in `plan_run`).
- Put docker calls behind a narrow adapter/interface so tests can assert call order/args without Docker.
- Inject time/sleep for readiness loops so tests stay fast and deterministic.

Verify
- `uv run --group lint ruff check .`
- `uv run --group lint ruff format .`
- `uv run pytest`
- Manual: run Agent + Interactive (with/without desktop) and confirm pull-before-terminal, no pre-pull pinging, correct cleanup.
