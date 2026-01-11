"""Settings collector for diagnostics bundles."""

import json
import os
from typing import Any

from agents_runner.diagnostics.redaction import redact_secrets


# Allowlist of safe settings to include in diagnostics
SAFE_SETTINGS = {
    "use",
    "shell",
    "preflight_enabled",
    "active_environment_id",
    "interactive_terminal_id",
    "window_w",
    "window_h",
    "max_agents_running",
    "append_pixelarch_context",
    "headless_desktop_enabled",
}

# Settings that may contain sensitive paths or should be excluded
EXCLUDED_SETTINGS = {
    "preflight_script",  # May contain sensitive commands
    "interactive_command",
    "interactive_command_claude",
    "interactive_command_copilot",
    "interactive_command_gemini",
}


def collect_settings(settings_data: dict[str, object] | None = None) -> dict[str, Any]:
    """
    Collect application settings for diagnostics bundle.
    
    Only includes safe settings from an allowlist and applies redaction
    to any remaining content for extra safety.
    
    Args:
        settings_data: Optional settings dictionary to collect from.
                      If None, attempts to collect from common sources.
    
    Returns:
        Dictionary of safe, redacted settings
    """
    if settings_data is None:
        settings_data = {}
    
    safe_settings: dict[str, Any] = {}
    
    # Collect only allowlisted settings
    for key, value in settings_data.items():
        if key in SAFE_SETTINGS:
            # Convert to JSON-serializable types
            if isinstance(value, (str, int, float, bool, type(None))):
                safe_settings[key] = value
            else:
                safe_settings[key] = str(value)
    
    # Add environment information (non-sensitive)
    safe_settings["env_info"] = {
        "CODEX_HOST_WORKDIR": bool(os.environ.get("CODEX_HOST_WORKDIR")),
        "CODEX_HOST_CODEX_DIR": bool(os.environ.get("CODEX_HOST_CODEX_DIR")),
        "AGENTS_RUNNER_STATE_PATH": bool(os.environ.get("AGENTS_RUNNER_STATE_PATH")),
    }
    
    # Apply redaction to the entire structure as a safety measure
    settings_json = json.dumps(safe_settings, indent=2)
    settings_json = redact_secrets(settings_json)
    
    return json.loads(settings_json)


def format_settings(settings: dict[str, Any]) -> str:
    """
    Format settings dictionary as a readable string.
    
    Args:
        settings: Settings dictionary
        
    Returns:
        Formatted string representation
    """
    return json.dumps(settings, indent=2, sort_keys=True)
