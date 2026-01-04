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
    """Represents a configured agent instance with a unique ID."""
    instance_id: str  # Unique ID for this instance (e.g., "agent-abc123")
    agent_type: str  # Type: "codex", "claude", or "copilot"
    config_dir: str = ""  # Config directory for this instance
    fallback_instance_id: str = ""  # ID of fallback agent instance


@dataclass
class AgentSelection:
    agent_instances: list[AgentInstance] = field(default_factory=list)
    selection_mode: str = "round-robin"
    
    # Legacy fields for backwards compatibility (populated on load, not used for save)
    enabled_agents: list[str] = field(default_factory=list)
    agent_config_dirs: dict[str, str] = field(default_factory=dict)
    agent_fallbacks: dict[str, str] = field(default_factory=dict)
    
    def __post_init__(self) -> None:
        """Auto-populate legacy fields from agent_instances if needed."""
        if self.agent_instances and not self.enabled_agents:
            # Build legacy format from new format for backwards compatibility
            self.enabled_agents = [inst.agent_type for inst in self.agent_instances]
            self.agent_config_dirs = {
                inst.agent_type: inst.config_dir 
                for inst in self.agent_instances 
                if inst.config_dir
            }
            # Build fallback mapping by resolving instance IDs to agent types
            instance_map = {inst.instance_id: inst.agent_type for inst in self.agent_instances}
            self.agent_fallbacks = {
                inst.agent_type: instance_map.get(inst.fallback_instance_id, "")
                for inst in self.agent_instances
                if inst.fallback_instance_id and inst.fallback_instance_id in instance_map
            }


@dataclass
class Environment:
    env_id: str
    name: str
    color: str = "emerald"
    host_workdir: str = ""
    host_codex_dir: str = ""
    agent_cli_args: str = ""
    max_agents_running: int = -1
    preflight_enabled: bool = False
    preflight_script: str = ""
    env_vars: dict[str, str] = field(default_factory=dict)
    extra_mounts: list[str] = field(default_factory=list)
    gh_management_mode: str = GH_MANAGEMENT_NONE
    gh_management_target: str = ""
    gh_management_locked: bool = False
    gh_use_host_cli: bool = True
    gh_pr_metadata_enabled: bool = False
    prompts: list[PromptConfig] = field(default_factory=list)
    prompts_unlocked: bool = False
    agent_selection: AgentSelection | None = None

    def normalized_color(self) -> str:
        value = (self.color or "").strip().lower()
        return value if value in ALLOWED_STAINS else "slate"
