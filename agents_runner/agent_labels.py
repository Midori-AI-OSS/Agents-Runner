from __future__ import annotations

from agents_runner.agent_systems import get_agent_system


def format_agent_ui_label(agent_name: str) -> str:
    """Return a friendly UI label for an agent or setup target."""

    normalized = str(agent_name or "").strip().lower()
    if not normalized:
        return "Unknown"

    try:
        plugin = get_agent_system(normalized)
    except Exception:
        plugin = None

    display_name = str(getattr(plugin, "display_name", "") or "").strip()
    if display_name:
        return display_name

    if normalized == "github":
        return "GitHub"

    words = normalized.replace("-", " ").replace("_", " ").split()
    if not words:
        return "Unknown"
    return " ".join(word.capitalize() for word in words)
