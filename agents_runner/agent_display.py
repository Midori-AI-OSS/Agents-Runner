"""Agent display name and GitHub URL mappings."""

from __future__ import annotations

AGENT_DISPLAY_NAMES = {
    "codex": "OpenAI Codex",
    "claude": "Claude Code",
    "copilot": "Github Copilot",
    "gemini": "Google Gemini",
    "opencode": "OpenCode",
    "opencode-tui": "OpenCode TUI",
    "opencode-web": "OpenCode Web",
    "qwen": "Qwen",
}

AGENT_GITHUB_URLS = {
    "claude": "https://github.com/anthropics/claude-code",
    "codex": "https://github.com/openai/codex",
    "copilot": "https://github.com/github/copilot-cli",
    "gemini": "https://github.com/google-gemini/gemini-cli",
    "opencode": "https://github.com/anomalyco/opencode",
    "opencode-tui": "https://github.com/anomalyco/opencode",
    "opencode-web": "https://github.com/anomalyco/opencode",
    "qwen": "https://github.com/QwenLM/qwen-code",
}


def get_agent_display_name(agent_cli: str) -> str:
    """Get the display name for an agent CLI."""
    normalized = str(agent_cli or "").strip().lower()
    return AGENT_DISPLAY_NAMES.get(normalized, agent_cli)


def get_agent_github_url(agent_cli: str) -> str:
    """Get the GitHub URL for an agent CLI."""
    normalized = str(agent_cli or "").strip().lower()
    return AGENT_GITHUB_URLS.get(normalized, "")


def format_agent_markdown_link(agent_cli: str) -> str:
    """Format agent as a markdown link."""
    display_name = get_agent_display_name(agent_cli)
    github_url = get_agent_github_url(agent_cli)
    if github_url:
        return f"[{display_name}]({github_url})"
    return display_name
