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

AGENTSNOVA_AUTO_MODE_INHERIT = "inherit"
AGENTSNOVA_AUTO_MODE_ENABLED = "enabled"
AGENTSNOVA_AUTO_MODE_DISABLED = "disabled"
AGENTSNOVA_AUTO_MODES = (
    AGENTSNOVA_AUTO_MODE_INHERIT,
    AGENTSNOVA_AUTO_MODE_ENABLED,
    AGENTSNOVA_AUTO_MODE_DISABLED,
)

AGENTSNOVA_MARKER_COMMENT_MODE_INHERIT = "inherit"
AGENTSNOVA_MARKER_COMMENT_MODE_KEEP = "keep"
AGENTSNOVA_MARKER_COMMENT_MODE_DELETE_AFTER_15S = "delete_after_15s"
AGENTSNOVA_MARKER_COMMENT_MODE_DISABLED = "disabled"
AGENTSNOVA_MARKER_COMMENT_MODES = (
    AGENTSNOVA_MARKER_COMMENT_MODE_INHERIT,
    AGENTSNOVA_MARKER_COMMENT_MODE_KEEP,
    AGENTSNOVA_MARKER_COMMENT_MODE_DELETE_AFTER_15S,
    AGENTSNOVA_MARKER_COMMENT_MODE_DISABLED,
)

GH_BRANCH_WORK_MODE_TASK_BRANCH = "task_branch"
GH_BRANCH_WORK_MODE_DIRECT_BASE = "direct_base"
GH_BRANCH_WORK_MODES = (
    GH_BRANCH_WORK_MODE_TASK_BRANCH,
    GH_BRANCH_WORK_MODE_DIRECT_BASE,
)

GH_TASK_BRANCH_NAMING_STYLE_STANDARD = "standard"
GH_TASK_BRANCH_NAMING_STYLE_SONGS = "songs"
GH_TASK_BRANCH_NAMING_STYLE_FOODS = "foods"
GH_TASK_BRANCH_NAMING_STYLE_ANIMALS = "animals"
GH_TASK_BRANCH_NAMING_STYLE_COLORS = "colors"
GH_TASK_BRANCH_NAMING_STYLE_SPACE = "space"
GH_TASK_BRANCH_NAMING_STYLE_CUSTOM = "custom"
GH_TASK_BRANCH_NAMING_STYLES = (
    GH_TASK_BRANCH_NAMING_STYLE_STANDARD,
    GH_TASK_BRANCH_NAMING_STYLE_SONGS,
    GH_TASK_BRANCH_NAMING_STYLE_FOODS,
    GH_TASK_BRANCH_NAMING_STYLE_ANIMALS,
    GH_TASK_BRANCH_NAMING_STYLE_COLORS,
    GH_TASK_BRANCH_NAMING_STYLE_SPACE,
    GH_TASK_BRANCH_NAMING_STYLE_CUSTOM,
)
GH_TASK_BRANCH_CUSTOM_TEMPLATE_DEFAULT = "{task_id}"

INTERACTIVE_PR_NO_PROMPT_MODE_AUTO_CREATE = "auto_create_pr"
INTERACTIVE_PR_NO_PROMPT_MODE_MANUAL_REVIEW = "manual_via_review_menu"
INTERACTIVE_PR_NO_PROMPT_MODES = (
    INTERACTIVE_PR_NO_PROMPT_MODE_AUTO_CREATE,
    INTERACTIVE_PR_NO_PROMPT_MODE_MANUAL_REVIEW,
)

GPU_OVERRIDE_MODE_INHERIT = "inherit"
GPU_OVERRIDE_MODE_ENABLED = "enabled"
GPU_OVERRIDE_MODE_DISABLED = "disabled"
GPU_OVERRIDE_MODES = (
    GPU_OVERRIDE_MODE_INHERIT,
    GPU_OVERRIDE_MODE_ENABLED,
    GPU_OVERRIDE_MODE_DISABLED,
)

OPENCODE_INTERACTIVE_MODE_TERMINAL = "terminal"
OPENCODE_INTERACTIVE_MODE_WEB = "web"
OPENCODE_INTERACTIVE_MODE_ASK = "ask"
OPENCODE_INTERACTIVE_MODES = (
    OPENCODE_INTERACTIVE_MODE_TERMINAL,
    OPENCODE_INTERACTIVE_MODE_WEB,
    OPENCODE_INTERACTIVE_MODE_ASK,
)
OPENCODE_INTERACTIVE_OVERRIDE_INHERIT = "inherit"
OPENCODE_INTERACTIVE_OVERRIDE_MODES = (
    OPENCODE_INTERACTIVE_OVERRIDE_INHERIT,
    OPENCODE_INTERACTIVE_MODE_TERMINAL,
    OPENCODE_INTERACTIVE_MODE_WEB,
    OPENCODE_INTERACTIVE_MODE_ASK,
)


def normalize_workspace_type(value: str) -> str:
    """Normalize workspace type to canonical values."""
    if not value or value == "none":
        return WORKSPACE_NONE
    if value in ("github", "git", "repo", "cloned"):
        return WORKSPACE_CLONED
    if value in ("local", "folder", "mounted"):
        return WORKSPACE_MOUNTED
    return WORKSPACE_NONE


def normalize_agentsnova_auto_mode(value: str) -> str:
    """Normalize additive AgentsNova automation mode values."""
    normalized = str(value or "").strip().lower()
    if normalized in AGENTSNOVA_AUTO_MODES:
        return normalized
    return AGENTSNOVA_AUTO_MODE_INHERIT


def normalize_agentsnova_marker_comment_mode(value: str) -> str:
    """Normalize additive AgentsNova marker-comment mode values."""
    normalized = str(value or "").strip().lower()
    if normalized in AGENTSNOVA_MARKER_COMMENT_MODES:
        return normalized
    return AGENTSNOVA_MARKER_COMMENT_MODE_INHERIT


def normalize_gh_branch_work_mode(value: str) -> str:
    """Normalize environment Git branch work mode values."""
    normalized = str(value or "").strip().lower()
    if normalized in GH_BRANCH_WORK_MODES:
        return normalized
    return GH_BRANCH_WORK_MODE_TASK_BRANCH


def normalize_gh_task_branch_naming_style(value: str) -> str:
    """Normalize environment task-branch naming style values."""
    normalized = str(value or "").strip().lower()
    if normalized in GH_TASK_BRANCH_NAMING_STYLES:
        return normalized
    return GH_TASK_BRANCH_NAMING_STYLE_STANDARD


def normalize_gh_task_branch_custom_template(value: str) -> str:
    """Normalize custom task-branch template text."""
    normalized = str(value or "").strip()
    return normalized or GH_TASK_BRANCH_CUSTOM_TEMPLATE_DEFAULT


def normalize_interactive_pr_no_prompt_mode(value: str) -> str:
    """Normalize interactive PR behavior when the prompt is disabled."""
    normalized = str(value or "").strip().lower()
    if normalized in INTERACTIVE_PR_NO_PROMPT_MODES:
        return normalized
    return INTERACTIVE_PR_NO_PROMPT_MODE_AUTO_CREATE


def normalize_gpu_override_mode(value: str) -> str:
    """Normalize environment-level GPU override mode values."""
    normalized = str(value or "").strip().lower()
    if normalized in GPU_OVERRIDE_MODES:
        return normalized
    return GPU_OVERRIDE_MODE_INHERIT


def normalize_opencode_interactive_mode(value: str) -> str:
    """Normalize global OpenCode interactive launch mode values."""
    normalized = str(value or "").strip().lower()
    if normalized in OPENCODE_INTERACTIVE_MODES:
        return normalized
    return OPENCODE_INTERACTIVE_MODE_TERMINAL


def normalize_opencode_interactive_override(value: str) -> str:
    """Normalize environment-level OpenCode interactive launch mode overrides."""
    normalized = str(value or "").strip().lower()
    if normalized in OPENCODE_INTERACTIVE_OVERRIDE_MODES:
        return normalized
    return OPENCODE_INTERACTIVE_OVERRIDE_INHERIT


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

    ``config_id`` references an :class:`~agents_runner.agent_configs.model.AgentConfig`
    stored in application state.
    """

    agent_id: str
    config_id: str = ""


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
    agent_cli_args: str = ""
    max_agents_running: int = -1
    headless_desktop_enabled: bool = False
    gpu_override_mode: str = GPU_OVERRIDE_MODE_INHERIT
    opencode_interactive_mode: str = OPENCODE_INTERACTIVE_OVERRIDE_INHERIT
    cache_desktop_build: bool = False
    container_caching_enabled: bool = False
    cache_system_preflight_enabled: bool = False
    cache_settings_preflight_enabled: bool = False
    env_vars: dict[str, str] = field(default_factory=dict)
    extra_mounts: list[str] = field(default_factory=list)
    env_vars_advanced_mode: bool = False
    mounts_advanced_mode: bool = False
    env_vars_advanced_acknowledged: bool = False
    mounts_advanced_acknowledged: bool = False
    ports: list[str] = field(default_factory=list)
    ports_unlocked: bool = False
    ports_advanced_acknowledged: bool = False
    gh_management_locked: bool = False
    workspace_type: str = WORKSPACE_NONE
    workspace_target: str = ""
    gh_last_base_branch: str = ""
    gh_use_host_cli: bool = True
    gh_context_enabled: bool = False  # Renamed from gh_pr_metadata_enabled
    github_polling_enabled: bool = False
    agentsnova_trusted_users_env: list[str] = field(default_factory=list)
    agentsnova_trusted_mode: str = "inherit"
    agentsnova_auto_review_mode: str = AGENTSNOVA_AUTO_MODE_INHERIT
    agentsnova_auto_reactions_mode: str = AGENTSNOVA_AUTO_MODE_INHERIT
    agentsnova_marker_comment_mode: str = AGENTSNOVA_MARKER_COMMENT_MODE_INHERIT
    interactive_pr_prompt_enabled: bool = True
    interactive_pr_no_prompt_mode: str = INTERACTIVE_PR_NO_PROMPT_MODE_AUTO_CREATE
    setup_agents_missing_prompt_enabled: bool = False
    interactive_pull_before_run_enabled: bool = True
    gh_branch_work_mode: str = GH_BRANCH_WORK_MODE_TASK_BRANCH
    gh_task_branch_naming_style: str = GH_TASK_BRANCH_NAMING_STYLE_STANDARD
    gh_task_branch_custom_template: str = GH_TASK_BRANCH_CUSTOM_TEMPLATE_DEFAULT
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
