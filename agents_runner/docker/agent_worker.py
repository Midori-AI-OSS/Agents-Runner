"""Main Docker agent worker orchestrator."""

import os
from typing import Any, Callable
from threading import Event

from agents_runner.prompt_sanitizer import sanitize_prompt
from agents_runner.agent_systems.registry import discover_plugins

from agents_runner.docker.config import DockerRunnerConfig
from agents_runner.docker.agent_worker_github import GitHubOperations
from agents_runner.docker.agent_worker_setup import WorkerSetup
from agents_runner.docker.agent_worker_container import ContainerExecutor


class DockerAgentWorker:
    """Orchestrates Docker-based agent task execution.

    Coordinates GitHub repository preparation, runtime environment setup,
    and container execution for agent tasks.
    """

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
        self._executor: ContainerExecutor | None = None
        self._gh_repo_root: str | None = None
        self._gh_base_branch: str | None = None
        self._gh_branch: str | None = None
        self._collected_artifacts: list[str] = []

    @property
    def container_id(self) -> str | None:
        """Get the current container ID."""
        # Check executor first for live container ID during execution
        if self._executor and self._executor.container_id:
            return self._executor.container_id
        return self._container_id

    @property
    def gh_repo_root(self) -> str | None:
        """Get the GitHub repository root path."""
        return self._gh_repo_root

    @property
    def gh_base_branch(self) -> str | None:
        """Get the GitHub base branch name."""
        return self._gh_base_branch

    @property
    def gh_branch(self) -> str | None:
        """Get the GitHub task branch name."""
        return self._gh_branch

    def request_stop(self) -> None:
        """Request graceful container stop."""
        from agents_runner.docker.process import _run_docker

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
        """Force-kill the container immediately."""
        from agents_runner.docker.process import _run_docker

        self._stop.set()
        if self._container_id:
            try:
                _run_docker(["kill", self._container_id], timeout_s=10.0)
            except Exception:
                pass

    def run(self) -> None:
        """Execute the agent task in a Docker container.

        Orchestrates:
        1. GitHub repository preparation
        2. Runtime environment setup
        3. Container execution and monitoring
        """
        # Initialize agent system plugins for capability checks (e.g., requires_github_token)
        discover_plugins()

        preflight_tmp_paths: list[str] = []

        try:
            # Step 1: Prepare GitHub repository (if configured)
            if self._config.gh_repo:
                try:
                    (
                        self._gh_repo_root,
                        self._gh_base_branch,
                        self._gh_branch,
                    ) = GitHubOperations.prepare_github_repo(
                        self._config,
                        self._on_log,
                        self._on_done,
                    )
                except Exception:
                    # GitHubOperations already called on_done, just return
                    return

            # Step 2: Prepare runtime environment
            os.makedirs(self._config.host_codex_dir, exist_ok=True)
            setup = WorkerSetup(
                self._config, self._prompt, self._on_log, self._on_state
            )
            runtime_env = setup.prepare_runtime_environment(preflight_tmp_paths)

            # Step 3: Execute container
            executor = ContainerExecutor(
                self._config,
                runtime_env,
                self._on_state,
                self._on_log,
                self._stop,
            )
            self._executor = executor
            exit_code = executor.execute_container()

            # Update state
            self._container_id = executor.container_id
            # TODO: artifacts collection will be handled in future work

            # Report completion
            self._on_done(exit_code, None, self._collected_artifacts)

        except Exception as exc:
            self._on_done(1, str(exc), self._collected_artifacts)
        finally:
            # Clean up temporary preflight scripts
            for tmp_path in preflight_tmp_paths:
                try:
                    if os.path.exists(tmp_path):
                        os.unlink(tmp_path)
                except Exception:
                    pass
