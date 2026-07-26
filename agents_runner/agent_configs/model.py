from dataclasses import dataclass


@dataclass
class AgentConfig:
    config_id: str
    agent_cli: str
    config_dir: str = ""
    cli_flags: str = ""
    agent: str = ""
    model: str = ""
    variant: str = ""
