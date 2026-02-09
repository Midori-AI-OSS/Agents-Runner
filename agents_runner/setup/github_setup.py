"""GitHub CLI setup helper commands.

This module is intentionally separate from agent-system plugins: GitHub is used
for authentication and repository operations, but it is not an agent runtime.
"""


def get_setup_command() -> str:
    return "gh auth login; read -p 'Press Enter to close...'"


def get_config_command() -> str:
    return "gh config list; read -p 'Press Enter to close...'"


def get_verify_command() -> str:
    return "gh --version"
