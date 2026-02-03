from dataclasses import dataclass
from dataclasses import field


@dataclass(frozen=True)
class DockerRunnerConfig:
    task_id: str
    image: str
    host_codex_dir: str
    host_workdir: str
    agent_cli: str = "codex"
    container_codex_dir: str = "/home/midori-ai/.codex"
    container_workdir: str = "/home/midori-ai/workspace"
    auto_remove: bool = True
    pull_before_run: bool = True
    settings_preflight_script: str | None = None
    environment_preflight_script: str | None = None
    headless_desktop_enabled: bool = False
    desktop_cache_enabled: bool = False
    container_caching_enabled: bool = False
    cached_preflight_script: str | None = None
    environment_id: str = ""
    # Use a task-specific filename by default to avoid collisions when multiple
    # runs share a container or temp directory.
    container_settings_preflight_path: str = (
        "/tmp/agents-runner-preflight-settings-{task_id}.sh"
    )
    container_environment_preflight_path: str = (
        "/tmp/agents-runner-preflight-environment-{task_id}.sh"
    )
    env_vars: dict[str, str] = field(default_factory=dict)
    extra_mounts: list[str] = field(default_factory=list)
    agent_cli_args: list[str] = field(default_factory=list)
    # GitHub repo preparation
    gh_repo: str | None = None
    gh_prefer_gh_cli: bool = True
    gh_recreate_if_needed: bool = True
    gh_base_branch: str | None = None
    gh_context_file_path: str | None = None  # Host path to GitHub context file
    # Hard timeout for post-run artifact collection/finalization (best-effort).
    artifact_collection_timeout_s: float = 30.0
    # Optional override for container name (for testing or custom naming)
    container_name: str | None = None
