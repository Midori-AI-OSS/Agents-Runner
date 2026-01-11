"""Diagnostics bundle builder for issue reporting."""

import json
import os
import platform
import sys
import zipfile
from datetime import datetime
from typing import Any

from agents_runner.diagnostics.log_collector import collect_logs
from agents_runner.diagnostics.paths import bundles_dir
from agents_runner.diagnostics.redaction import redact_secrets
from agents_runner.diagnostics.settings_collector import collect_settings
from agents_runner.diagnostics.settings_collector import format_settings
from agents_runner.diagnostics.task_collector import collect_task_state
from agents_runner.diagnostics.task_collector import format_task_state


def get_app_version() -> str:
    """
    Get the application version.
    
    Returns:
        Version string
    """
    # Read from pyproject.toml
    try:
        import tomllib
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        pyproject_path = os.path.join(project_root, "pyproject.toml")
        
        if os.path.exists(pyproject_path):
            with open(pyproject_path, "rb") as f:
                data = tomllib.load(f)
                return data.get("project", {}).get("version", "unknown")
    except Exception:
        pass
    
    return "unknown"


def collect_system_info() -> dict[str, Any]:
    """
    Collect system and application information.
    
    Returns:
        Dictionary of system info
    """
    return {
        "app_version": get_app_version(),
        "python_version": sys.version,
        "os_system": platform.system(),
        "os_release": platform.release(),
        "os_version": platform.version(),
        "platform": platform.platform(),
        "architecture": platform.machine(),
    }


def create_diagnostics_bundle(
    settings_data: dict[str, object] | None = None
) -> str:
    """
    Create a comprehensive diagnostics bundle for issue reporting.
    
    Collects:
    - Application version and system information
    - Application settings (filtered and redacted)
    - Recent task logs (redacted)
    - Task state information
    
    Args:
        settings_data: Optional settings dictionary to include
        
    Returns:
        Path to the created diagnostics bundle zip file
    """
    # Create timestamp for filename
    timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    bundle_filename = f"diagnostics-{timestamp}.zip"
    bundle_path = os.path.join(bundles_dir(), bundle_filename)
    
    # Collect all diagnostics data
    system_info = collect_system_info()
    settings = collect_settings(settings_data)
    task_state = collect_task_state()
    logs = collect_logs()
    
    # Create zip bundle
    with zipfile.ZipFile(bundle_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # Add system info
        info_content = json.dumps(system_info, indent=2)
        zf.writestr("info/system.json", info_content)
        
        # Add settings
        settings_content = format_settings(settings)
        settings_content = redact_secrets(settings_content)
        zf.writestr("info/settings.json", settings_content)
        
        # Add task state
        task_state_content = format_task_state(task_state)
        task_state_content = redact_secrets(task_state_content)
        zf.writestr("tasks/state.json", task_state_content)
        
        # Add logs (each as separate file)
        for log_filename, log_content in logs.items():
            # Apply redaction to all logs
            redacted_content = redact_secrets(log_content)
            zf.writestr(f"logs/{log_filename}", redacted_content)
        
        # Add README explaining bundle contents
        readme = """Diagnostics Bundle Contents
===========================

This bundle contains diagnostic information for issue reporting.

Structure:
- info/system.json: Application version and system information
- info/settings.json: Application settings (secrets redacted)
- tasks/state.json: Task state and history information
- logs/: Recent task logs (secrets redacted)

All sensitive information (tokens, keys, passwords, etc.) has been
automatically redacted and replaced with [REDACTED].

Please attach this bundle to your issue report.
"""
        zf.writestr("README.txt", readme)
    
    return bundle_path
