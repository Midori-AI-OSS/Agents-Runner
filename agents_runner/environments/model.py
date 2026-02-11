from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field


ENVIRONMENT_VERSION = 1
ENVIRONMENT_FILENAME_PREFIX = "environment-"

SYSTEM_ENV_ID = "_system"
SYSTEM_ENV_NAME = "System"

ALLOWED_STAINS = (
    "slate",
    "cyan",
    "emerald",
    "violet",
    "rose",
    "amber",
    "blue",
    "teal",
    "lime",
    "fuchsia",
    "indigo",
    "orange",
)

WORKSPACE_NONE = "none"
WORKSPACE_MOUNTED = "mounted"
WORKSPACE_CLONED = "cloned"


def normalize_workspace_type(value: str) -> str:
    """Normalize workspace type to canonical values."""
    if not value or value == "none":
        return WORKSPACE_NONE
    if value in ("github", "git", "repo", "cloned"):
        return WORKSPACE_CLONED
    if value in ("local", "folder", "mounted"):
        return WORKSPACE_MOUNTED
    return WORKSPACE_NONE


@dataclass
class PromptConfig:
    enabled: bool = False
    text: str = ""
    prompt_path: str = ""


@dataclass
class AgentInstance:
    """A single, ordered agent entry for an environment.

    ``agent_id`` must be unique within the environment so it can be referenced by
    fallback mappings and UI controls.
    """

    agent_id: str
    agent_cli: str
    config_dir: str = ""
    cli_flags: str = ""


@dataclass
class AgentSelection:
    agents: list[AgentInstance] = field(default_factory=list)
    selection_mode: str = "round-robin"
    agent_fallbacks: dict[str, str] = field(default_factory=dict)
    pinned_agent_id: str = ""


@dataclass
class Environment:
    env_id: str
    name: str
    color: str = "emerald"
    host_workdir: str = ""
    host_codex_dir: str = ""
    agent_cli_args: str = ""
    max_agents_running: int = -1
    headless_desktop_enabled: bool = False
    cache_desktop_build: bool = False
    container_caching_enabled: bool = False
    cached_preflight_script: str = ""
    preflight_enabled: bool = False
    preflight_script: str = ""
    env_vars: dict[str, str] = field(default_factory=dict)
    extra_mounts: list[str] = field(default_factory=list)
    ports: list[str] = field(default_factory=list)
    ports_unlocked: bool = False
    ports_advanced_acknowledged: bool = False
    gh_management_locked: bool = False
    workspace_type: str = WORKSPACE_NONE
    workspace_target: str = ""
    gh_last_base_branch: str = ""
    gh_use_host_cli: bool = True
    gh_context_enabled: bool = False  # Renamed from gh_pr_metadata_enabled
    prompts: list[PromptConfig] = field(default_factory=list)
    prompts_unlocked: bool = False
    agent_selection: AgentSelection | None = None
    use_cross_agents: bool = False
    cross_agent_allowlist: list[str] = field(default_factory=list)
    midoriai_template_likelihood: float = 0.0
    midoriai_template_detected: bool = False
    midoriai_template_detected_path: str | None = None
    _cached_is_git_repo: bool | None = None

    def normalized_color(self) -> str:
        value = (self.color or "").strip().lower()
        return value if value in ALLOWED_STAINS else "slate"

    def detect_git_if_mounted_folder(self) -> bool:
        """Detect if mounted folder environment is a git repository.

        This method caches the result to avoid repeated git operations.
        Only applicable for mounted folder (local) environments.

        Returns:
            True if folder is a git repo, False otherwise.
            False for non-mounted-folder environments.
        """
        # Only applies to mounted folders
        if self.workspace_type != WORKSPACE_MOUNTED:
            return False

        # Return cached result if available
        if self._cached_is_git_repo is not None:
            return self._cached_is_git_repo

        # Detect git
        from agents_runner.environments.git_operations import get_git_info

        folder_path = self.workspace_target
        if not folder_path:
            self._cached_is_git_repo = False
            return False

        git_info = get_git_info(folder_path)
        self._cached_is_git_repo = git_info is not None
        return self._cached_is_git_repo
