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

GH_MANAGEMENT_NONE = "none"
GH_MANAGEMENT_LOCAL = "local"
GH_MANAGEMENT_GITHUB = "github"


def normalize_gh_management_mode(value: str) -> str:
    mode = (value or "").strip().lower()
    if mode in {GH_MANAGEMENT_LOCAL, GH_MANAGEMENT_GITHUB}:
        return mode
    return GH_MANAGEMENT_NONE


@dataclass
class PromptConfig:
    enabled: bool = False
    text: str = ""


@dataclass
class AgentInstance:
    """A single, ordered agent entry for an environment.

    ``agent_id`` must be unique within the environment so it can be referenced by
    fallback mappings and UI controls.
    """

    agent_id: str
    agent_cli: str
    config_dir: str = ""


@dataclass
class AgentSelection:
    agents: list[AgentInstance] = field(default_factory=list)
    selection_mode: str = "round-robin"
    agent_fallbacks: dict[str, str] = field(default_factory=dict)


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
    preflight_enabled: bool = False
    preflight_script: str = ""
    env_vars: dict[str, str] = field(default_factory=dict)
    extra_mounts: list[str] = field(default_factory=list)
    gh_management_mode: str = GH_MANAGEMENT_NONE
    gh_management_target: str = ""
    gh_management_locked: bool = False
    gh_last_base_branch: str = ""
    gh_use_host_cli: bool = True
    gh_pr_metadata_enabled: bool = False
    prompts: list[PromptConfig] = field(default_factory=list)
    prompts_unlocked: bool = False
    agent_selection: AgentSelection | None = None

    def normalized_color(self) -> str:
        value = (self.color or "").strip().lower()
        return value if value in ALLOWED_STAINS else "slate"
